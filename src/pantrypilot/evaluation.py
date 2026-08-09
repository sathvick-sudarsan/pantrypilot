import argparse
import json
import sys
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pantrypilot.ingredients import (
    INGREDIENT_REGISTRY,
    IngredientRegistry,
    resolve_ingredient,
)
from pantrypilot.normalization import normalize_ingredient


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input: str
    expected_ingredient_id: str | None
    category: Literal["canonical", "alias", "unresolved"]

    @field_validator("input")
    @classmethod
    def normalize_input(cls, value: str) -> str:
        return normalize_ingredient(value)


class EvaluationFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    cases: tuple[EvaluationCase, ...] = Field(min_length=1)

    @field_validator("cases")
    @classmethod
    def reject_duplicate_inputs(
        cls, cases: tuple[EvaluationCase, ...]
    ) -> tuple[EvaluationCase, ...]:
        seen: set[str] = set()
        for case in cases:
            if case.input in seen:
                raise ValueError(f"duplicate evaluation input: {case.input}")
            seen.add(case.input)
        return cases


class EvaluationPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input: str
    category: Literal["canonical", "alias", "unresolved"]
    expected_ingredient_id: str | None
    predicted_ingredient_id: str | None


class ResolutionMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    false_positive_cases: tuple[EvaluationPrediction, ...]
    false_negative_cases: tuple[EvaluationPrediction, ...]


class ResolverComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_schema_version: int
    exact_name_baseline: ResolutionMetrics
    canonical_alias_resolver: ResolutionMetrics
    recall_improved: bool
    zero_false_positives: bool


def load_evaluation_fixture(
    path: Path,
    ingredient_registry: IngredientRegistry,
) -> EvaluationFixture:
    fixture = EvaluationFixture.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )
    for case in fixture.cases:
        if (
            case.expected_ingredient_id is not None
            and case.expected_ingredient_id not in ingredient_registry.by_id
        ):
            raise ValueError(
                f"unknown expected ingredient id: {case.expected_ingredient_id}"
            )
    return fixture


def evaluate_resolver(
    cases: Sequence[EvaluationCase],
    resolver: Callable[[str], str | None],
) -> ResolutionMetrics:
    true_positives = 0
    false_positives: list[EvaluationPrediction] = []
    false_negatives: list[EvaluationPrediction] = []
    true_negatives = 0

    for case in cases:
        predicted_id = resolver(case.input)
        prediction = EvaluationPrediction(
            input=case.input,
            category=case.category,
            expected_ingredient_id=case.expected_ingredient_id,
            predicted_ingredient_id=predicted_id,
        )
        if case.expected_ingredient_id is None:
            if predicted_id is None:
                true_negatives += 1
            else:
                false_positives.append(prediction)
        elif predicted_id == case.expected_ingredient_id:
            true_positives += 1
        else:
            false_negatives.append(prediction)
            if predicted_id is not None:
                false_positives.append(prediction)

    false_positive_count = len(false_positives)
    false_negative_count = len(false_negatives)
    precision_denominator = true_positives + false_positive_count
    recall_denominator = true_positives + false_negative_count
    return ResolutionMetrics(
        true_positives=true_positives,
        false_positives=false_positive_count,
        false_negatives=false_negative_count,
        true_negatives=true_negatives,
        precision=round(true_positives / precision_denominator, 4)
        if precision_denominator
        else 0.0,
        recall=round(true_positives / recall_denominator, 4)
        if recall_denominator
        else 0.0,
        false_positive_cases=tuple(false_positives),
        false_negative_cases=tuple(false_negatives),
    )


def resolve_exact_name(
    value: str,
    ingredient_registry: IngredientRegistry,
) -> str | None:
    normalized = normalize_ingredient(value)
    ingredient_id = ingredient_registry.by_term.get(normalized)
    if ingredient_id is None:
        return None
    ingredient = ingredient_registry.by_id[ingredient_id]
    return ingredient_id if normalized == ingredient.canonical_name else None


def _resolve_canonical_alias(
    value: str,
    ingredient_registry: IngredientRegistry,
) -> str | None:
    return resolve_ingredient(value, ingredient_registry).ingredient_id


def compare_resolvers(
    fixture: EvaluationFixture,
    ingredient_registry: IngredientRegistry,
) -> ResolverComparison:
    baseline = evaluate_resolver(
        fixture.cases,
        partial(resolve_exact_name, ingredient_registry=ingredient_registry),
    )
    resolver = evaluate_resolver(
        fixture.cases,
        partial(_resolve_canonical_alias, ingredient_registry=ingredient_registry),
    )
    return ResolverComparison(
        fixture_schema_version=fixture.schema_version,
        exact_name_baseline=baseline,
        canonical_alias_resolver=resolver,
        recall_improved=resolver.recall > baseline.recall,
        zero_false_positives=resolver.false_positives == 0,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate PantryPilot ingredient resolution."
    )
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)
    try:
        fixture = load_evaluation_fixture(args.fixture, INGREDIENT_REGISTRY)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(
            json.dumps(
                {"error": f"invalid evaluation fixture: {exc}"},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    comparison = compare_resolvers(fixture, INGREDIENT_REGISTRY)
    print(comparison.model_dump_json(indent=2))
    return 0 if comparison.recall_improved and comparison.zero_false_positives else 1


if __name__ == "__main__":
    raise SystemExit(main())
