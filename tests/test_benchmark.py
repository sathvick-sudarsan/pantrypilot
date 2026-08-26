import copy
import hashlib
import json
from pathlib import Path

import pytest

from pantrypilot import benchmark as benchmark_module
from pantrypilot.benchmark import main, nearest_rank_percentile, run_benchmark
from pantrypilot.catalog_release import CatalogRelease, current_catalog_release
from pantrypilot.ingredients import INGREDIENT_REGISTRY, resolve_ingredients
from pantrypilot.models import RankingRequest, RankingResponse, Recipe
from pantrypilot.ranking import is_eligible, rank_recipes

FIXTURE_PATH = Path(__file__).parents[1] / "benchmarks" / "full-scan-ranking-v1.json"
CATALOG_DIGEST = "f811853765a0732ae34521e47c2f7e3c691f5cb00bfec4e138f9ce08a01c9f2c"
WORKLOAD_IDS = {
    "broad-high-coverage",
    "broad-low-coverage",
    "strict-preparation-limit",
    "common-hard-exclusion",
    "high-protein-target",
    "typical-limited-response",
}
REQUEST_FIELDS = {
    "pantry_items",
    "min_protein_g",
    "max_prep_minutes",
    "excluded_ingredients",
    "limit",
}
SMALL_RESPONSE_DIGEST = (
    "16338a9577e2c8fa9db01571e170055a050a9a92122a7f19267d66642857c7cf"
)

SEMANTIC_REQUESTS = {
    "broad-high-coverage": {
        "pantry_items": [
            "eggs",
            "spinach",
            "olive oil",
            "rice",
            "tomatoes",
            "onion",
            "garlic",
            "carrots",
            "avocado",
            "lime",
            "black bean",
            "chicken",
        ],
        "min_protein_g": 25.0,
        "max_prep_minutes": 60,
        "excluded_ingredients": [],
        "limit": 50,
    },
    "broad-low-coverage": {
        "pantry_items": ["lentil", "cardamom pods"],
        "min_protein_g": 20.0,
        "max_prep_minutes": 60,
        "excluded_ingredients": [],
        "limit": 50,
    },
    "strict-preparation-limit": {
        "pantry_items": [
            "egg",
            "bread",
            "avocado",
            "spinach",
            "olive oil",
            "oats",
            "banana",
            "yogurt",
            "peanut",
        ],
        "min_protein_g": 20.0,
        "max_prep_minutes": 20,
        "excluded_ingredients": [],
        "limit": 50,
    },
    "common-hard-exclusion": {
        "pantry_items": [
            "rice",
            "tomato",
            "onion",
            "garlic",
            "carrot",
            "spinach",
            "olive oil",
            "chicken",
        ],
        "min_protein_g": 25.0,
        "max_prep_minutes": 60,
        "excluded_ingredients": ["garlic"],
        "limit": 50,
    },
    "high-protein-target": {
        "pantry_items": [
            "chicken",
            "tuna",
            "salmon",
            "eggs",
            "spinach",
            "rice",
            "tomato",
            "garlic",
            "olive oil",
        ],
        "min_protein_g": 50.0,
        "max_prep_minutes": 60,
        "excluded_ingredients": [],
        "limit": 50,
    },
    "typical-limited-response": {
        "pantry_items": [
            "rice",
            "chickpea",
            "tomato",
            "onion",
            "garlic",
            "spinach",
            "carrot",
            "olive oil",
        ],
        "min_protein_g": 25.0,
        "max_prep_minutes": 30,
        "excluded_ingredients": ["chicken"],
        "limit": 5,
    },
}

EXPECTED_IDENTITIES = {
    "broad-high-coverage": {
        "expected_eligible_count": 24,
        "expected_response_ids": [
            "spinach-omelet",
            "black-bean-quinoa-salad",
            "black-bean-rice-bowl",
            "avocado-egg-toast",
            "tuna-avocado-salad",
            "chicken-tacos",
            "black-bean-tacos",
            "coconut-lentil-curry",
            "tomato-lentil-stew",
            "chicken-pasta-bowl",
            "coconut-chicken-stew",
            "chickpea-rice-bowl",
            "chickpea-cucumber-salad",
            "pasta-tomato-soup",
            "lentil-cucumber-salad",
            "salmon-quinoa-salad",
            "beef-rice-bowl",
            "potato-chickpea-curry",
            "tofu-rice-bowl",
            "tofu-vegetable-soup",
            "lentil-soup",
            "peanut-noodles",
            "yogurt-oat-bowl",
            "overnight-oats",
        ],
        "expected_response_digest": (
            "c4caf4c6260ea59b76ce7a115d3473b6544ef18c1dda471900f16a4377582cd5"
        ),
    },
    "broad-low-coverage": {
        "expected_eligible_count": 24,
        "expected_response_ids": [
            "lentil-soup",
            "lentil-cucumber-salad",
            "coconut-lentil-curry",
            "tomato-lentil-stew",
            "spinach-omelet",
            "tuna-avocado-salad",
            "peanut-noodles",
            "avocado-egg-toast",
            "chicken-tacos",
            "chickpea-rice-bowl",
            "salmon-quinoa-salad",
            "black-bean-tacos",
            "beef-rice-bowl",
            "black-bean-quinoa-salad",
            "black-bean-rice-bowl",
            "tofu-rice-bowl",
            "tofu-vegetable-soup",
            "yogurt-oat-bowl",
            "chicken-pasta-bowl",
            "overnight-oats",
            "coconut-chicken-stew",
            "chickpea-cucumber-salad",
            "potato-chickpea-curry",
            "pasta-tomato-soup",
        ],
        "expected_response_digest": (
            "5fb98708a6d0ae29e33c070e23553b39f4eb5306f13e85e05311cf84b76b5533"
        ),
    },
    "strict-preparation-limit": {
        "expected_eligible_count": 8,
        "expected_response_ids": [
            "avocado-egg-toast",
            "spinach-omelet",
            "yogurt-oat-bowl",
            "overnight-oats",
            "peanut-noodles",
            "tuna-avocado-salad",
            "chickpea-cucumber-salad",
            "lentil-cucumber-salad",
        ],
        "expected_response_digest": (
            "8afe1680cc7946f00e2d1c196dd542bc88a4401a0a0c2d5eff0b85b0c0c7c30e"
        ),
    },
    "common-hard-exclusion": {
        "expected_eligible_count": 16,
        "expected_response_ids": [
            "spinach-omelet",
            "chickpea-rice-bowl",
            "chickpea-cucumber-salad",
            "tuna-avocado-salad",
            "black-bean-rice-bowl",
            "lentil-cucumber-salad",
            "chicken-tacos",
            "salmon-quinoa-salad",
            "black-bean-quinoa-salad",
            "avocado-egg-toast",
            "tofu-vegetable-soup",
            "lentil-soup",
            "peanut-noodles",
            "black-bean-tacos",
            "yogurt-oat-bowl",
            "overnight-oats",
        ],
        "expected_response_digest": (
            "f2b97f109348315a964a6c394e48571e4ce3f10e841cdf20263398e59565763f"
        ),
    },
    "high-protein-target": {
        "expected_eligible_count": 24,
        "expected_response_ids": [
            "spinach-omelet",
            "chicken-pasta-bowl",
            "salmon-quinoa-salad",
            "avocado-egg-toast",
            "tuna-avocado-salad",
            "coconut-lentil-curry",
            "tomato-lentil-stew",
            "pasta-tomato-soup",
            "potato-chickpea-curry",
            "chickpea-cucumber-salad",
            "chickpea-rice-bowl",
            "chicken-tacos",
            "black-bean-rice-bowl",
            "beef-rice-bowl",
            "lentil-cucumber-salad",
            "coconut-chicken-stew",
            "tofu-rice-bowl",
            "black-bean-quinoa-salad",
            "tofu-vegetable-soup",
            "yogurt-oat-bowl",
            "peanut-noodles",
            "overnight-oats",
            "black-bean-tacos",
            "lentil-soup",
        ],
        "expected_response_digest": (
            "b825203f321e8e2f5fda7a4567bef168b2630544af12589308f43569f150d662"
        ),
    },
    "typical-limited-response": {
        "expected_eligible_count": 11,
        "expected_response_ids": [
            "spinach-omelet",
            "chickpea-cucumber-salad",
            "chickpea-rice-bowl",
            "tuna-avocado-salad",
            "lentil-cucumber-salad",
        ],
        "expected_response_digest": (
            "d4f51d15a55ed3fe286364dde510b0c472cf514b584b788b41e83b479dec3647"
        ),
    },
}


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _small_release() -> CatalogRelease:
    return CatalogRelease(
        version=9,
        manifest_digest="a" * 64,
        recipes=(
            Recipe(
                id="quick-eggs",
                name="Quick Eggs",
                required_ingredient_ids=("eggs",),
                calories=100,
                protein_g=12.0,
                prep_minutes=5,
            ),
        ),
        retired_recipe_ids=(),
    )


def _small_fixture(*, warmups: int = 1, measurements: int = 4) -> dict[str, object]:
    return {
        "schema_version": 1,
        "catalog_version": 9,
        "catalog_digest": "a" * 64,
        "catalog_size": 1,
        "warmups": warmups,
        "measurements": measurements,
        "workloads": [
            {
                "id": "small",
                "request": {
                    "pantry_items": ["egg"],
                    "min_protein_g": 10.0,
                    "max_prep_minutes": 20,
                    "excluded_ingredients": [],
                    "limit": 5,
                },
                "expected_eligible_count": 1,
                "expected_response_ids": ["quick-eggs"],
                "expected_response_digest": SMALL_RESPONSE_DIGEST,
            }
        ],
    }


def _response_digest(response: RankingResponse) -> str:
    payload = json.dumps(
        response.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_committed_fixture_pins_the_approved_release_and_workloads():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture["schema_version"] == 1
    assert fixture["catalog_version"] == 1
    assert fixture["catalog_digest"] == CATALOG_DIGEST
    assert fixture["catalog_size"] == 24
    assert fixture["warmups"] == 100
    assert fixture["measurements"] == 1_000
    workloads = {workload["id"]: workload for workload in fixture["workloads"]}
    assert set(workloads) == WORKLOAD_IDS
    assert len(workloads) == len(fixture["workloads"])

    for workload_id, workload in workloads.items():
        assert set(workload["request"]) == REQUEST_FIELDS
        assert workload["request"] == SEMANTIC_REQUESTS[workload_id]
        assert {
            key: workload[key]
            for key in (
                "expected_eligible_count",
                "expected_response_ids",
                "expected_response_digest",
            )
        } == EXPECTED_IDENTITIES[workload_id]

    resolutions = {
        workload_id: resolve_ingredients(
            workload["request"]["pantry_items"], INGREDIENT_REGISTRY
        )
        for workload_id, workload in workloads.items()
    }
    unresolved = [
        (workload_id, resolution.input)
        for workload_id, workload_resolutions in resolutions.items()
        for resolution in workload_resolutions
        if resolution.match_type == "unresolved"
    ]
    assert unresolved == [("broad-low-coverage", "cardamom pods")]
    assert all(
        resolution.match_type != "unresolved"
        for workload in workloads.values()
        for resolution in resolve_ingredients(
            workload["request"]["excluded_ingredients"], INGREDIENT_REGISTRY
        )
    )


def test_committed_fixture_response_identities_match_the_production_release():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    release = current_catalog_release(INGREDIENT_REGISTRY)

    for workload in fixture["workloads"]:
        request = RankingRequest.model_validate(workload["request"])
        response = rank_recipes(request, release.recipes, INGREDIENT_REGISTRY)
        excluded_ids = {
            resolution.ingredient_id
            for resolution in resolve_ingredients(
                request.excluded_ingredients, INGREDIENT_REGISTRY
            )
            if resolution.ingredient_id is not None
        }
        eligible_count = sum(
            is_eligible(recipe, excluded_ids, request.max_prep_minutes)
            for recipe in release.recipes
        )

        assert eligible_count == workload["expected_eligible_count"]
        assert [result.id for result in response.results] == workload[
            "expected_response_ids"
        ]
        assert _response_digest(response) == workload["expected_response_digest"]


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("schema_version", 2),
        ("catalog_version", 0),
        ("catalog_digest", "not-a-digest"),
        ("catalog_size", 0),
        ("warmups", -1),
        ("measurements", 0),
        ("workloads", []),
    ],
)
def test_fixture_rejects_invalid_required_values(
    tmp_path: Path, field: str, invalid_value: object
):
    fixture = _small_fixture()
    fixture[field] = invalid_value

    with pytest.raises(ValueError):
        run_benchmark(_write_fixture(tmp_path, fixture), clock=lambda: 0)


def test_fixture_rejects_float_schema_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fixture = _small_fixture()
    fixture["schema_version"] = 1.0
    monkeypatch.setattr(
        benchmark_module,
        "current_catalog_release",
        lambda registry: _small_release(),
    )

    with pytest.raises(ValueError, match="schema_version"):
        run_benchmark(_write_fixture(tmp_path, fixture), clock=lambda: 0)


@pytest.mark.parametrize("missing_field", ["catalog_version", "catalog_digest"])
def test_fixture_requires_release_identity(tmp_path: Path, missing_field: str):
    fixture = _small_fixture()
    fixture.pop(missing_field)

    with pytest.raises(ValueError):
        run_benchmark(_write_fixture(tmp_path, fixture), clock=lambda: 0)


def test_fixture_rejects_duplicate_workload_ids(tmp_path: Path):
    fixture = _small_fixture()
    fixture["workloads"].append(copy.deepcopy(fixture["workloads"][0]))

    with pytest.raises(ValueError, match="duplicate workload id"):
        run_benchmark(_write_fixture(tmp_path, fixture), clock=lambda: 0)


@pytest.mark.parametrize("request_change", ["missing", "extra"])
def test_fixture_requires_the_exact_ranking_request_fields(
    tmp_path: Path, request_change: str
):
    fixture = _small_fixture()
    request = fixture["workloads"][0]["request"]
    if request_change == "missing":
        request.pop("limit")
    else:
        request["unexpected"] = True

    with pytest.raises(ValueError, match="request fields"):
        run_benchmark(_write_fixture(tmp_path, fixture), clock=lambda: 0)


def test_fixture_rejects_unresolved_exclusions_before_timing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fixture = _small_fixture()
    fixture["workloads"][0]["request"]["excluded_ingredients"] = ["mystery"]
    monkeypatch.setattr(
        benchmark_module,
        "current_catalog_release",
        lambda registry: _small_release(),
    )

    with pytest.raises(ValueError, match="unresolved exclusions"):
        run_benchmark(
            _write_fixture(tmp_path, fixture),
            clock=lambda: pytest.fail("clock must not run"),
        )


@pytest.mark.parametrize(
    ("field", "drifted_value"),
    [
        ("catalog_version", 2),
        ("catalog_digest", "0" * 64),
        ("catalog_size", 23),
    ],
)
def test_release_drift_fails_before_timing(
    tmp_path: Path, field: str, drifted_value: object
):
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fixture[field] = drifted_value

    with pytest.raises(ValueError, match="release"):
        run_benchmark(
            _write_fixture(tmp_path, fixture),
            clock=lambda: pytest.fail("clock must not run"),
        )


@pytest.mark.parametrize(
    ("samples", "percentile", "expected"),
    [
        ([4, 1, 3, 2], 0.95, 4),
        ([5, 1, 3, 2, 4], 0.95, 5),
        ([40, 10, 30, 20], 0.50, 20),
    ],
)
def test_nearest_rank_percentile_uses_the_ceiling_rank(
    samples: list[int], percentile: float, expected: int
):
    assert nearest_rank_percentile(samples, percentile) == expected


def test_fake_clock_drives_integer_sample_statistics_and_complete_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fixture_path = _write_fixture(tmp_path, _small_fixture())
    clock_values = iter(
        [
            0,
            1_000_000,
            10_000_000,
            15_000_000,
            20_000_000,
            22_000_000,
            30_000_000,
            34_000_000,
        ]
    )
    monkeypatch.setattr(
        benchmark_module,
        "current_catalog_release",
        lambda registry: _small_release(),
    )

    result = run_benchmark(fixture_path, clock=lambda: next(clock_values))

    assert list(result) == [
        "catalog_digest",
        "catalog_size",
        "catalog_version",
        "fixture_schema_version",
        "fixture_sha256",
        "git_commit",
        "machine",
        "measurements",
        "os",
        "platform",
        "processor",
        "python_implementation",
        "python_version",
        "run_at_utc",
        "warmups",
        "workloads",
    ]
    assert (
        result["fixture_sha256"]
        == hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    )
    assert result["catalog_version"] == 9
    assert result["catalog_digest"] == "a" * 64
    assert result["catalog_size"] == 1
    assert result["warmups"] == 1
    assert result["measurements"] == 4
    assert all(
        isinstance(result[field], str) and result[field]
        for field in (
            "git_commit",
            "os",
            "platform",
            "python_implementation",
            "python_version",
            "run_at_utc",
        )
    )
    assert all(isinstance(result[field], str) for field in ("machine", "processor"))
    assert result["workloads"] == [
        {
            "catalog_size": 1,
            "eligible_count": 1,
            "id": "small",
            "max_ms": 5.0,
            "median_ms": 3.0,
            "min_ms": 1.0,
            "p95_ms": 5.0,
            "response_digest": SMALL_RESPONSE_DIGEST,
            "response_ids": ["quick-eggs"],
            "returned_count": 1,
        }
    ]


def test_each_measured_response_is_compared_after_the_end_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fixture_path = _write_fixture(tmp_path, _small_fixture(warmups=2, measurements=3))
    events: list[str] = []
    original_rank = rank_recipes
    original_equal = RankingResponse.__eq__

    def recording_rank(*args: object, **kwargs: object) -> RankingResponse:
        events.append("rank")
        return original_rank(*args, **kwargs)

    def recording_equal(self: RankingResponse, other: object) -> bool:
        events.append("compare")
        return original_equal(self, other)

    def clock() -> int:
        events.append("clock")
        return len(events)

    monkeypatch.setattr(
        benchmark_module,
        "current_catalog_release",
        lambda registry: _small_release(),
    )
    monkeypatch.setattr(benchmark_module, "rank_recipes", recording_rank)
    monkeypatch.setattr(RankingResponse, "__eq__", recording_equal)

    run_benchmark(fixture_path, clock=clock)

    assert events[-12:] == ["clock", "rank", "clock", "compare"] * 3
    assert events.count("compare") == 5


@pytest.mark.parametrize(
    ("warmups", "measurements", "drift_call"),
    [(1, 1, 2), (0, 2, 3)],
)
def test_response_drift_fails_during_warmup_or_measurement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    warmups: int,
    measurements: int,
    drift_call: int,
):
    fixture_path = _write_fixture(
        tmp_path, _small_fixture(warmups=warmups, measurements=measurements)
    )
    calls = 0

    def drifting_rank(*args: object, **kwargs: object) -> RankingResponse:
        nonlocal calls
        calls += 1
        response = rank_recipes(*args, **kwargs)
        if calls == drift_call:
            return response.model_copy(update={"returned_count": 0})
        return response

    monkeypatch.setattr(
        benchmark_module,
        "current_catalog_release",
        lambda registry: _small_release(),
    )
    monkeypatch.setattr(benchmark_module, "rank_recipes", drifting_rank)

    with pytest.raises(ValueError, match="nondeterministic"):
        run_benchmark(fixture_path, clock=iter(range(20)).__next__)


def test_main_prints_indented_json_with_sorted_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    fixture_path = tmp_path / "unused.json"
    monkeypatch.setattr(
        benchmark_module,
        "run_benchmark",
        lambda path: {"z": 1, "a": {"z": 2, "a": 3}},
    )

    assert main([str(fixture_path)]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ('{\n  "a": {\n    "a": 3,\n    "z": 2\n  },\n  "z": 1\n}\n')


def test_main_returns_one_json_error_object_for_an_invalid_fixture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    fixture_path = tmp_path / "invalid.json"
    fixture_path.write_text("{", encoding="utf-8")

    assert main([str(fixture_path)]) != 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert set(json.loads(captured.err)) == {"error"}
