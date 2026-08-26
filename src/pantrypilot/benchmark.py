import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from pantrypilot.catalog_release import current_catalog_release
from pantrypilot.ingredients import INGREDIENT_REGISTRY, resolve_ingredients
from pantrypilot.models import RankingRequest, RankingResponse
from pantrypilot.ranking import is_eligible, rank_recipes

FIXTURE_FIELDS = {
    "schema_version",
    "catalog_version",
    "catalog_digest",
    "catalog_size",
    "warmups",
    "measurements",
    "workloads",
}
WORKLOAD_FIELDS = {
    "id",
    "request",
    "expected_eligible_count",
    "expected_response_ids",
    "expected_response_digest",
}
REQUEST_FIELDS = {
    "pantry_items",
    "min_protein_g",
    "max_prep_minutes",
    "excluded_ingredients",
    "limit",
}


def _mapping(value: object, fields: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} must contain exactly the expected fields")
    return value


def _integer(value: object, label: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer of at least {minimum}")
    return value


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be lowercase 64-hex")
    return value


def _validate_fixture(value: object) -> dict[str, object]:
    fixture = _mapping(value, FIXTURE_FIELDS, "fixture")
    if _integer(fixture["schema_version"], "schema_version", minimum=1) != 1:
        raise ValueError("fixture schema_version must be 1")
    _integer(fixture["catalog_version"], "catalog_version", minimum=1)
    _digest(fixture["catalog_digest"], "catalog_digest")
    _integer(fixture["catalog_size"], "catalog_size", minimum=1)
    _integer(fixture["warmups"], "warmups", minimum=0)
    _integer(fixture["measurements"], "measurements", minimum=1)

    workloads = fixture["workloads"]
    if not isinstance(workloads, list) or not workloads:
        raise ValueError("workloads must be a non-empty list")
    seen_ids: set[str] = set()
    for index, value in enumerate(workloads):
        workload = _mapping(value, WORKLOAD_FIELDS, f"workload {index}")
        workload_id = workload["id"]
        if not isinstance(workload_id, str) or not workload_id.strip():
            raise ValueError("workload id must be a non-blank string")
        if workload_id in seen_ids:
            raise ValueError(f"duplicate workload id: {workload_id}")
        seen_ids.add(workload_id)
        request = _mapping(
            workload["request"],
            REQUEST_FIELDS,
            f"workload {workload_id} request fields",
        )
        RankingRequest.model_validate(request)
        _integer(
            workload["expected_eligible_count"],
            f"workload {workload_id} expected_eligible_count",
            minimum=0,
        )
        response_ids = workload["expected_response_ids"]
        if (
            not isinstance(response_ids, list)
            or any(
                not isinstance(response_id, str) or not response_id.strip()
                for response_id in response_ids
            )
            or len(set(response_ids)) != len(response_ids)
        ):
            raise ValueError(
                f"workload {workload_id} expected_response_ids must be unique strings"
            )
        _digest(
            workload["expected_response_digest"],
            f"workload {workload_id} expected_response_digest",
        )
    return fixture


def _response_digest(response: RankingResponse) -> str:
    payload = json.dumps(
        response.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def nearest_rank_percentile(samples_ns: Sequence[int], percentile: float) -> int:
    if not samples_ns:
        raise ValueError("samples must not be empty")
    if (
        isinstance(percentile, bool)
        or not isinstance(percentile, (int, float))
        or not math.isfinite(percentile)
        or not 0 < percentile <= 1
    ):
        raise ValueError("percentile must be greater than zero and at most one")
    if any(
        isinstance(sample, bool) or not isinstance(sample, int) or sample < 0
        for sample in samples_ns
    ):
        raise ValueError("samples must be non-negative integer nanoseconds")
    ordered = sorted(samples_ns)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_benchmark(
    fixture_path: Path,
    *,
    clock: Callable[[], int] = time.perf_counter_ns,
) -> dict[str, object]:
    fixture_bytes = fixture_path.read_bytes()
    fixture = _validate_fixture(json.loads(fixture_bytes))
    release = current_catalog_release(INGREDIENT_REGISTRY)
    if (
        fixture["catalog_version"] != release.version
        or fixture["catalog_digest"] != release.manifest_digest
        or fixture["catalog_size"] != len(release.recipes)
    ):
        raise ValueError("benchmark fixture release identity does not match release")

    workload_results: list[dict[str, object]] = []
    for workload_value in fixture["workloads"]:
        workload = workload_value
        request = RankingRequest.model_validate(workload["request"])
        exclusion_resolutions = resolve_ingredients(
            request.excluded_ingredients, INGREDIENT_REGISTRY
        )
        if any(
            resolution.match_type == "unresolved"
            for resolution in exclusion_resolutions
        ):
            raise ValueError(
                f"workload {workload['id']} contains unresolved exclusions"
            )
        excluded_ids = {
            resolution.ingredient_id
            for resolution in exclusion_resolutions
            if resolution.ingredient_id is not None
        }
        eligible_count = sum(
            is_eligible(recipe, excluded_ids, request.max_prep_minutes)
            for recipe in release.recipes
        )
        validated_response = rank_recipes(request, release.recipes, INGREDIENT_REGISTRY)
        response_ids = [result.id for result in validated_response.results]
        response_digest = _response_digest(validated_response)
        if eligible_count != workload["expected_eligible_count"]:
            raise ValueError(f"workload {workload['id']} eligible count drift")
        if response_ids != workload["expected_response_ids"]:
            raise ValueError(f"workload {workload['id']} response id drift")
        if response_digest != workload["expected_response_digest"]:
            raise ValueError(f"workload {workload['id']} response digest drift")
        if validated_response.returned_count != len(workload["expected_response_ids"]):
            raise ValueError(f"workload {workload['id']} returned count drift")

        for _ in range(fixture["warmups"]):
            response = rank_recipes(request, release.recipes, INGREDIENT_REGISTRY)
            if response != validated_response:
                raise ValueError(
                    f"workload {workload['id']} produced nondeterministic warmup output"
                )

        samples_ns: list[int] = []
        for _ in range(fixture["measurements"]):
            start = clock()
            response = rank_recipes(request, release.recipes, INGREDIENT_REGISTRY)
            end = clock()
            samples_ns.append(end - start)
            if response != validated_response:
                raise ValueError(
                    f"workload {workload['id']} produced nondeterministic "
                    "measured output"
                )

        workload_results.append(
            {
                "catalog_size": len(release.recipes),
                "eligible_count": eligible_count,
                "id": workload["id"],
                "max_ms": max(samples_ns) / 1_000_000,
                "median_ms": statistics.median(samples_ns) / 1_000_000,
                "min_ms": min(samples_ns) / 1_000_000,
                "p95_ms": nearest_rank_percentile(samples_ns, 0.95) / 1_000_000,
                "response_digest": response_digest,
                "response_ids": response_ids,
                "returned_count": validated_response.returned_count,
            }
        )

    return {
        "catalog_digest": release.manifest_digest,
        "catalog_size": len(release.recipes),
        "catalog_version": release.version,
        "fixture_schema_version": fixture["schema_version"],
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "git_commit": _git_commit(),
        "machine": platform.machine(),
        "measurements": fixture["measurements"],
        "os": platform.system(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "run_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "warmups": fixture["warmups"],
        "workloads": workload_results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark full-scan recipe ranking.")
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_benchmark(args.fixture)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ) as exc:
        print(
            json.dumps({"error": f"benchmark failed: {exc}"}, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
