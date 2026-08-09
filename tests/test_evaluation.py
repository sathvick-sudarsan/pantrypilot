import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pantrypilot.evaluation import (
    EvaluationCase,
    compare_resolvers,
    evaluate_resolver,
    load_evaluation_fixture,
    main,
    resolve_exact_name,
)
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


def test_evaluate_resolver_uses_the_approved_confusion_count_rules():
    cases = (
        EvaluationCase(
            input="eggs",
            expected_ingredient_id="eggs",
            category="canonical",
        ),
        EvaluationCase(
            input="black bean",
            expected_ingredient_id="black-beans",
            category="alias",
        ),
        EvaluationCase(
            input="vegetable stock",
            expected_ingredient_id="vegetable-broth",
            category="alias",
        ),
        EvaluationCase(
            input="eggplant",
            expected_ingredient_id=None,
            category="unresolved",
        ),
        EvaluationCase(
            input="carrot cake",
            expected_ingredient_id=None,
            category="unresolved",
        ),
    )
    predictions = {
        "eggs": "eggs",
        "black bean": None,
        "vegetable stock": "peanuts",
        "eggplant": "eggs",
        "carrot cake": None,
    }

    metrics = evaluate_resolver(cases, predictions.get)

    assert (
        metrics.true_positives,
        metrics.false_positives,
        metrics.false_negatives,
        metrics.true_negatives,
    ) == (1, 2, 2, 1)
    assert metrics.precision == 0.3333
    assert metrics.recall == 0.3333
    assert [case.input for case in metrics.false_positive_cases] == [
        "vegetable stock",
        "eggplant",
    ]
    assert [case.input for case in metrics.false_negative_cases] == [
        "black bean",
        "vegetable stock",
    ]

    all_abstained = evaluate_resolver(cases[:1], lambda _value: None)
    assert all_abstained.precision == 0.0
    assert all_abstained.recall == 0.0


def test_evaluate_resolver_counts_correct_resolutions_abstentions_and_over_resolution():
    cases = (
        EvaluationCase(
            input="eggs",
            expected_ingredient_id="eggs",
            category="canonical",
        ),
        EvaluationCase(
            input="black bean",
            expected_ingredient_id="black-beans",
            category="alias",
        ),
        EvaluationCase(
            input="eggplant",
            expected_ingredient_id=None,
            category="unresolved",
        ),
    )
    predictions = {
        "eggs": "eggs",
        "black bean": None,
        "eggplant": "eggs",
    }

    metrics = evaluate_resolver(cases, predictions.get)

    assert (
        metrics.true_positives,
        metrics.false_positives,
        metrics.false_negatives,
        metrics.true_negatives,
    ) == (1, 1, 1, 0)
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5


@pytest.mark.parametrize(
    ("value", "expected_id"),
    [
        (" BLACK BEANS ", "black-beans"),
        ("black bean", None),
        ("eggplant", None),
    ],
)
def test_exact_name_baseline_uses_normalized_canonical_names_only(value, expected_id):
    assert resolve_exact_name(value, INGREDIENT_REGISTRY) == expected_id


def test_v1_comparison_improves_recall_with_zero_false_positives():
    fixture = load_evaluation_fixture(FIXTURE_PATH, INGREDIENT_REGISTRY)

    comparison = compare_resolvers(fixture, INGREDIENT_REGISTRY)

    baseline = comparison.exact_name_baseline
    resolver = comparison.canonical_alias_resolver
    assert (
        baseline.true_positives,
        baseline.false_positives,
        baseline.false_negatives,
        baseline.true_negatives,
    ) == (14, 0, 7, 7)
    assert baseline.precision == 1.0
    assert baseline.recall == 0.6667
    assert [case.input for case in baseline.false_negative_cases] == [
        "egg",
        "black bean",
        "corn tortilla",
        "peanut",
        "lentil",
        "carrot",
        "vegetable stock",
    ]
    assert (
        resolver.true_positives,
        resolver.false_positives,
        resolver.false_negatives,
        resolver.true_negatives,
    ) == (21, 0, 0, 7)
    assert resolver.precision == 1.0
    assert resolver.recall == 1.0
    assert resolver.false_positive_cases == ()
    assert resolver.false_negative_cases == ()
    assert comparison.recall_improved is True
    assert comparison.zero_false_positives is True


def test_evaluation_cli_prints_deterministic_comparison_json(capsys):
    exit_code = main([str(FIXTURE_PATH)])

    first_output = capsys.readouterr().out
    assert exit_code == 0
    parsed = json.loads(first_output)
    assert parsed["exact_name_baseline"]["recall"] == 0.6667
    assert parsed["canonical_alias_resolver"]["recall"] == 1.0
    assert parsed["recall_improved"] is True
    assert parsed["zero_false_positives"] is True

    assert main([str(FIXTURE_PATH)]) == 0
    assert capsys.readouterr().out == first_output


def test_evaluation_cli_fails_when_an_acceptance_threshold_is_missed(tmp_path, capsys):
    no_improvement_path = write_fixture(
        tmp_path,
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "eggplant",
                    "expected_ingredient_id": "eggs",
                    "category": "alias",
                }
            ],
        },
    )

    exit_code = main([str(no_improvement_path)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["recall_improved"] is False

    false_positive_path = tmp_path / "false-positive.json"
    false_positive_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "input": "black bean",
                        "expected_ingredient_id": "black-beans",
                        "category": "alias",
                    },
                    {
                        "input": "egg",
                        "expected_ingredient_id": None,
                        "category": "unresolved",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([str(false_positive_path)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["recall_improved"] is True
    assert output["zero_false_positives"] is False


def test_evaluation_cli_reports_invalid_fixture_without_traceback(tmp_path, capsys):
    path = tmp_path / "invalid.json"
    path.write_text("{", encoding="utf-8")

    exit_code = main([str(path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert json.loads(captured.err)["error"].startswith("invalid evaluation fixture:")
