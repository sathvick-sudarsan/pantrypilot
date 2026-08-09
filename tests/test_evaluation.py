import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pantrypilot.evaluation import load_evaluation_fixture
from pantrypilot.ingredients import INGREDIENT_REGISTRY, resolve_ingredient

FIXTURE_PATH = Path("evaluations/ingredient-resolution-v1.json")


def test_load_evaluation_fixture_validates_version_and_case_shape(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "input": " Black Bean ",
                        "expected_ingredient_id": "black-beans",
                        "category": "alias",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    fixture = load_evaluation_fixture(path, INGREDIENT_REGISTRY)

    assert fixture.schema_version == 1
    assert fixture.cases[0].input == "black bean"
    assert fixture.cases[0].expected_ingredient_id == "black-beans"
    assert fixture.cases[0].category == "alias"


def write_fixture(tmp_path, data) -> Path:
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "data",
    [
        {"schema_version": 2, "cases": []},
        {"schema_version": 1, "cases": []},
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "   ",
                    "expected_ingredient_id": None,
                    "category": "unresolved",
                }
            ],
        },
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "unknown",
                    "expected_ingredient_id": None,
                    "category": "negative",
                }
            ],
        },
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "unknown",
                    "expected_ingredient_id": None,
                    "category": "unresolved",
                    "notes": "not approved",
                }
            ],
        },
        {
            "schema_version": 1,
            "cases": [],
            "dataset_name": "future",
        },
    ],
)
def test_load_evaluation_fixture_rejects_invalid_schema(tmp_path, data):
    with pytest.raises((ValidationError, ValueError)):
        load_evaluation_fixture(
            write_fixture(tmp_path, data),
            INGREDIENT_REGISTRY,
        )


def test_evaluation_fixture_models_are_frozen(tmp_path):
    fixture = load_evaluation_fixture(
        write_fixture(
            tmp_path,
            {
                "schema_version": 1,
                "cases": [
                    {
                        "input": "eggs",
                        "expected_ingredient_id": "eggs",
                        "category": "canonical",
                    }
                ],
            },
        ),
        INGREDIENT_REGISTRY,
    )

    with pytest.raises(ValidationError):
        fixture.schema_version = 2
    with pytest.raises(ValidationError):
        fixture.cases[0].category = "alias"


def test_load_evaluation_fixture_rejects_duplicate_normalized_inputs(tmp_path):
    path = write_fixture(
        tmp_path,
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "black bean",
                    "expected_ingredient_id": "black-beans",
                    "category": "alias",
                },
                {
                    "input": " BLACK BEAN ",
                    "expected_ingredient_id": "black-beans",
                    "category": "alias",
                },
            ],
        },
    )

    with pytest.raises(ValidationError, match="duplicate evaluation input"):
        load_evaluation_fixture(path, INGREDIENT_REGISTRY)


def test_load_evaluation_fixture_rejects_unknown_expected_id(tmp_path):
    path = write_fixture(
        tmp_path,
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "future ingredient",
                    "expected_ingredient_id": "future-ingredient",
                    "category": "canonical",
                }
            ],
        },
    )

    with pytest.raises(
        ValueError,
        match="unknown expected ingredient id: future-ingredient",
    ):
        load_evaluation_fixture(path, INGREDIENT_REGISTRY)


def test_v1_fixture_covers_all_registered_terms_with_consistent_categories():
    fixture = load_evaluation_fixture(FIXTURE_PATH, INGREDIENT_REGISTRY)

    expected_registered_cases = {
        (ingredient.canonical_name, ingredient.id, "canonical")
        for ingredient in INGREDIENT_REGISTRY.by_id.values()
    } | {
        (alias, ingredient.id, "alias")
        for ingredient in INGREDIENT_REGISTRY.by_id.values()
        for alias in ingredient.aliases
    }
    actual_registered_cases = {
        (case.input, case.expected_ingredient_id, case.category)
        for case in fixture.cases
        if case.category != "unresolved"
    }

    assert actual_registered_cases == expected_registered_cases

    for case in fixture.cases:
        resolution = resolve_ingredient(case.input, INGREDIENT_REGISTRY)
        if case.category == "unresolved":
            assert case.expected_ingredient_id is None
            assert resolution.match_type == "unresolved"
            assert resolution.ingredient_id is None
        else:
            assert case.expected_ingredient_id is not None
            assert resolution.match_type == case.category
            assert resolution.ingredient_id == case.expected_ingredient_id

    assert {case.input for case in fixture.cases if case.category == "unresolved"} == {
        "eggplant",
        "black bean sauce",
        "tortilla chips",
        "peanut oil",
        "lentil pasta",
        "carrot cake",
        "vegetable shortening",
    }


def test_v1_fixture_has_the_approved_version_and_category_counts():
    fixture = load_evaluation_fixture(FIXTURE_PATH, INGREDIENT_REGISTRY)

    assert fixture.schema_version == 1
    assert len(fixture.cases) == 28
    assert sum(case.category == "canonical" for case in fixture.cases) == 14
    assert sum(case.category == "alias" for case in fixture.cases) == 7
    assert sum(case.category == "unresolved" for case in fixture.cases) == 7
