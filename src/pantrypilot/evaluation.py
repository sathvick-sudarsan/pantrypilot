import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pantrypilot.ingredients import IngredientRegistry
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
