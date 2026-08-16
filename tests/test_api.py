import json
import os
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pantrypilot.app as app_module
from pantrypilot.app import create_app
from pantrypilot.catalog_store import CatalogStoreError
from pantrypilot.models import Recipe


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(tmp_path / "catalog.sqlite3")) as test_client:
        yield test_client


@pytest.fixture
def safe_client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(
        create_app(tmp_path / "safe-catalog.sqlite3"),
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client


VALID_REQUEST = {
    "pantry_items": [" Eggs ", "spinach", "EGGS"],
    "min_protein_g": 25.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": ["peanuts"],
    "limit": 1,
}


def test_lifespan_initializes_and_publishes_frozen_catalog(tmp_path: Path) -> None:
    if create_app is None:
        pytest.fail("create_app is not implemented")

    database_path = tmp_path / "catalog.sqlite3"
    application = create_app(database_path)

    assert not database_path.exists()
    with TestClient(application) as client:
        assert database_path.exists()
        assert isinstance(client.app.state.recipe_catalog, tuple)
        assert all(
            isinstance(recipe, Recipe) for recipe in client.app.state.recipe_catalog
        )
        assert len(client.app.state.recipe_catalog) == 4


def test_importing_app_does_not_create_database(tmp_path: Path) -> None:
    database_path = tmp_path / "import-only.sqlite3"
    environment = os.environ.copy()
    environment["PANTRYPILOT_DB_PATH"] = str(database_path)

    completed = subprocess.run(
        [sys.executable, "-c", "import pantrypilot.app"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert not database_path.exists()


def test_persisted_non_empty_change_is_visible_after_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with TestClient(create_app(database_path)):
        pass
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE recipes SET name = ? WHERE id = ?",
            ("Durable Omelet", "spinach-omelet"),
        )

    with TestClient(create_app(database_path)) as restarted:
        response = restarted.post(
            "/v1/meal-rankings",
            json=VALID_REQUEST,
        )

    assert response.status_code == 200
    result = next(
        item for item in response.json()["results"] if item["id"] == "spinach-omelet"
    )
    assert result["name"] == "Durable Omelet"


def test_unavailable_storage_prevents_startup(tmp_path: Path) -> None:
    application = create_app(tmp_path)  # A directory cannot be a SQLite file.

    with pytest.raises(CatalogStoreError, match="catalog connection failed"):
        with TestClient(application):
            pass


def test_incomplete_current_schema_prevents_startup_without_seed_fallback(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 1")

    with pytest.raises(CatalogStoreError):
        with TestClient(create_app(database_path)):
            pass


def test_request_uses_snapshot_without_database_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = create_app(tmp_path / "catalog.sqlite3")
    with TestClient(application) as client:

        def fail_if_called(*args: object, **kwargs: object) -> None:
            raise AssertionError("request attempted database I/O")

        monkeypatch.setattr(app_module, "initialize_catalog", fail_if_called)
        monkeypatch.setattr(app_module, "load_durable_catalog", fail_if_called)

        response = client.post(
            "/v1/meal-rankings",
            json=VALID_REQUEST,
        )

    assert response.status_code == 200
    assert response.json()["returned_count"] >= 1


def test_meal_rankings_exposes_alias_duplicate_and_unresolved_pantry_evidence(client):
    response = client.post(
        "/v1/meal-rankings",
        json={
            "pantry_items": ["black bean", "black beans", "unknown"],
            "min_protein_g": 0.0,
            "max_prep_minutes": 30,
            "excluded_ingredients": ["peanut"],
            "limit": 50,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert [
        item["match_type"] for item in body["ingredient_resolution"]["pantry_items"]
    ] == [
        "alias",
        "canonical",
        "unresolved",
    ]
    assert [
        item["ingredient_id"] for item in body["ingredient_resolution"]["pantry_items"]
    ] == [
        "black-beans",
        "black-beans",
        None,
    ]
    assert body["ingredient_resolution"]["excluded_ingredients"][0] == {
        "input": "peanut",
        "normalized": "peanut",
        "ingredient_id": "peanuts",
        "canonical_name": "peanuts",
        "match_type": "alias",
    }
    assert "peanut-noodles" not in {result["id"] for result in body["results"]}


def test_meal_rankings_returns_fail_closed_422_for_unresolved_exclusion(client):
    response = client.post(
        "/v1/meal-rankings",
        json={
            **VALID_REQUEST,
            "pantry_items": [],
            "excluded_ingredients": ["groundnut"],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "type": "unresolved_excluded_ingredients",
            "message": "All excluded ingredients must resolve before ranking.",
            "ingredient_resolution": {
                "pantry_items": [],
                "excluded_ingredients": [
                    {
                        "input": "groundnut",
                        "normalized": "groundnut",
                        "ingredient_id": None,
                        "canonical_name": None,
                        "match_type": "unresolved",
                    }
                ],
            },
        }
    }


def test_meal_rankings_returns_known_catalog_result(client):
    response = client.post("/v1/meal-rankings", json=VALID_REQUEST)

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "id": "spinach-omelet",
                "name": "Spinach Omelet",
                "required_ingredients": ["eggs", "spinach", "olive oil"],
                "calories": 410,
                "protein_g": 28.0,
                "prep_minutes": 15,
                "final_score": 0.7167,
                "matched_ingredients": ["eggs", "spinach"],
                "missing_ingredients": ["olive oil"],
                "score_breakdown": {
                    "pantry_coverage": {
                        "value": 0.6667,
                        "weight": 0.7,
                        "contribution": 0.4667,
                    },
                    "protein_fit": {
                        "value": 1.0,
                        "weight": 0.2,
                        "contribution": 0.2,
                    },
                    "time_fit": {
                        "value": 0.5,
                        "weight": 0.1,
                        "contribution": 0.05,
                    },
                },
                "explanation": (
                    "Matched 2 of 3 required ingredients "
                    "(coverage 0.6667); 28.0g protein meets the "
                    "25.0g target (fit 1.0000); 15 minutes is within "
                    "the 30-minute limit (fit 0.5000)."
                ),
            }
        ],
        "returned_count": 1,
        "ingredient_resolution": {
            "pantry_items": [
                {
                    "input": " Eggs ",
                    "normalized": "eggs",
                    "ingredient_id": "eggs",
                    "canonical_name": "eggs",
                    "match_type": "canonical",
                },
                {
                    "input": "spinach",
                    "normalized": "spinach",
                    "ingredient_id": "spinach",
                    "canonical_name": "spinach",
                    "match_type": "canonical",
                },
                {
                    "input": "EGGS",
                    "normalized": "eggs",
                    "ingredient_id": "eggs",
                    "canonical_name": "eggs",
                    "match_type": "canonical",
                },
            ],
            "excluded_ingredients": [
                {
                    "input": "peanuts",
                    "normalized": "peanuts",
                    "ingredient_id": "peanuts",
                    "canonical_name": "peanuts",
                    "match_type": "canonical",
                }
            ],
        },
    }


def test_meal_rankings_returns_successful_empty_result(client):
    request = {
        **VALID_REQUEST,
        "pantry_items": [],
        "max_prep_minutes": 0,
        "excluded_ingredients": [],
        "limit": 5,
    }

    response = client.post("/v1/meal-rankings", json=request)

    assert response.status_code == 200
    assert response.json() == {
        "results": [],
        "returned_count": 0,
        "ingredient_resolution": {
            "pantry_items": [],
            "excluded_ingredients": [],
        },
    }


def test_meal_rankings_returns_all_eligible_results_in_deterministic_order(client):
    response = client.post(
        "/v1/meal-rankings",
        json={
            **VALID_REQUEST,
            "excluded_ingredients": [],
            "max_prep_minutes": 45,
            "limit": 50,
        },
    )

    response_body = response.json()
    assert response.status_code == 200
    assert [result["id"] for result in response_body["results"]] == [
        "spinach-omelet",
        "peanut-noodles",
        "black-bean-tacos",
        "lentil-soup",
    ]
    assert response_body["returned_count"] > 1
    assert response_body["returned_count"] == len(response_body["results"])


def test_canonical_inputs_preserve_feature_001_result_order_and_scores(client):
    response = client.post(
        "/v1/meal-rankings",
        json={
            **VALID_REQUEST,
            "excluded_ingredients": [],
            "max_prep_minutes": 45,
            "limit": 50,
        },
    )

    assert response.status_code == 200
    assert [
        (result["id"], result["final_score"]) for result in response.json()["results"]
    ] == [
        ("spinach-omelet", 0.7334),
        ("peanut-noodles", 0.2156),
        ("black-bean-tacos", 0.1964),
        ("lentil-soup", 0.176),
    ]


@pytest.mark.parametrize(
    "missing_field",
    [
        "pantry_items",
        "min_protein_g",
        "max_prep_minutes",
        "excluded_ingredients",
        "limit",
    ],
)
def test_meal_rankings_requires_every_request_field(client, missing_field):
    request = {**VALID_REQUEST}
    request.pop(missing_field)

    response = client.post("/v1/meal-rankings", json=request)

    assert response.status_code == 422
    assert missing_field in response.text


def test_meal_rankings_rejects_fractional_integer(client):
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, "max_prep_minutes": 30.5},
    )

    assert response.status_code == 422
    assert "max_prep_minutes" in response.text


def test_meal_rankings_rejects_malformed_json(client):
    response = client.post(
        "/v1/meal-rankings",
        content="{",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


def test_unexpected_error_returns_500_without_internal_details(
    safe_client, monkeypatch
):
    def fail_ranking(*_args, **_kwargs):
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr(app_module, "rank_recipes", fail_ranking)

    response = safe_client.post("/v1/meal-rankings", json=VALID_REQUEST)

    assert response.status_code == 500
    assert "private implementation detail" not in response.text


def test_identical_http_requests_return_identical_ordered_responses(client):
    first = client.post("/v1/meal-rankings", json=VALID_REQUEST)
    second = client.post("/v1/meal-rankings", json=VALID_REQUEST)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_protein_g", -0.1),
        ("max_prep_minutes", -1),
        ("limit", 0),
        ("limit", 51),
    ],
)
def test_meal_rankings_rejects_invalid_numeric_boundaries(client, field, value):
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, field: value},
    )

    assert response.status_code == 422
    assert field in response.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_protein_g", "25.0"),
        ("max_prep_minutes", True),
        ("limit", 5.0),
        ("limit", True),
    ],
)
def test_meal_rankings_rejects_wrong_numeric_types(client, field, value):
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, field: value},
    )

    assert response.status_code == 422
    assert field in response.text


@pytest.mark.parametrize(
    ("value", "rendered_input"),
    [
        (float("inf"), "Infinity"),
        (float("-inf"), "-Infinity"),
        (float("nan"), "NaN"),
    ],
)
def test_meal_rankings_preserves_non_finite_validation_details(
    safe_client, value, rendered_input
):
    response = safe_client.post(
        "/v1/meal-rankings",
        content=json.dumps({**VALID_REQUEST, "min_protein_g": value}),
        headers={"content-type": "application/json"},
    )

    error = response.json()["detail"][0]
    assert response.status_code == 422
    assert error == {
        "type": "finite_number",
        "loc": ["body", "min_protein_g"],
        "msg": "Input should be a finite number",
        "input": rendered_input,
    }


def test_meal_rankings_keeps_null_distinct_from_non_finite_values(safe_client):
    response = safe_client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, "min_protein_g": None},
    )

    error = response.json()["detail"][0]
    assert response.status_code == 422
    assert error == {
        "type": "float_type",
        "loc": ["body", "min_protein_g"],
        "msg": "Input should be a valid number",
        "input": None,
    }


def test_unknown_field_with_nested_non_finite_values_returns_serializable_422(
    safe_client,
):
    response = safe_client.post(
        "/v1/meal-rankings",
        content=json.dumps(
            {
                **VALID_REQUEST,
                "ranking_options": {
                    "positive": float("inf"),
                    "negative": float("-inf"),
                    "not_a_number": float("nan"),
                },
            }
        ),
        headers={"content-type": "application/json"},
    )

    error = response.json()["detail"][0]
    assert response.status_code == 422
    assert error == {
        "type": "extra_forbidden",
        "loc": ["body", "ranking_options"],
        "msg": "Extra inputs are not permitted",
        "input": {
            "positive": "Infinity",
            "negative": "-Infinity",
            "not_a_number": "NaN",
        },
    }


@pytest.mark.parametrize(
    ("request_update", "expected_field"),
    [
        ({"max_prep_minutes": float("nan")}, "max_prep_minutes"),
        ({"limit": float("inf")}, "limit"),
        ({"pantry_items": ["eggs", float("-inf")]}, "pantry_items"),
        ({"excluded_ingredients": [float("nan")]}, "excluded_ingredients"),
        ({"ranking_options": {"weight": float("inf")}}, "ranking_options"),
    ],
)
def test_meal_rankings_rejects_non_finite_values_anywhere_in_payload(
    safe_client, request_update, expected_field
):
    response = safe_client.post(
        "/v1/meal-rankings",
        content=json.dumps({**VALID_REQUEST, **request_update}),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert expected_field in response.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pantry_items", ["eggs", "   "]),
        ("excluded_ingredients", [""]),
    ],
)
def test_meal_rankings_rejects_blank_ingredient_values(safe_client, field, value):
    response = safe_client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, field: value},
    )

    error = response.json()["detail"][0]
    assert response.status_code == 422
    assert error["loc"] == ["body", field]
    assert error["type"] == "value_error"
    assert error["msg"] == "Value error, ingredient values must not be blank"
    assert error["input"] == value


def test_meal_rankings_rejects_unknown_request_fields(client):
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, "ranking_model": "future"},
    )

    error = response.json()["detail"][0]
    assert response.status_code == 422
    assert error == {
        "type": "extra_forbidden",
        "loc": ["body", "ranking_model"],
        "msg": "Extra inputs are not permitted",
        "input": "future",
    }
