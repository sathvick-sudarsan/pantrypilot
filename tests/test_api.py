import json

import pytest
from fastapi.testclient import TestClient

import pantrypilot.app as app_module

client = TestClient(app_module.app)
safe_client = TestClient(app_module.app, raise_server_exceptions=False)


VALID_REQUEST = {
    "pantry_items": [" Eggs ", "spinach", "EGGS"],
    "min_protein_g": 25.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": ["peanuts"],
    "limit": 1,
}


def test_meal_rankings_returns_known_catalog_result():
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
    }


def test_meal_rankings_returns_successful_empty_result():
    request = {
        **VALID_REQUEST,
        "pantry_items": [],
        "max_prep_minutes": 0,
        "excluded_ingredients": [],
        "limit": 5,
    }

    response = client.post("/v1/meal-rankings", json=request)

    assert response.status_code == 200
    assert response.json() == {"results": [], "returned_count": 0}


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
def test_meal_rankings_requires_every_request_field(missing_field):
    request = {**VALID_REQUEST}
    request.pop(missing_field)

    response = client.post("/v1/meal-rankings", json=request)

    assert response.status_code == 422
    assert missing_field in response.text


def test_meal_rankings_rejects_fractional_integer():
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, "max_prep_minutes": 30.5},
    )

    assert response.status_code == 422
    assert "max_prep_minutes" in response.text


def test_meal_rankings_rejects_malformed_json():
    response = client.post(
        "/v1/meal-rankings",
        content="{",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


def test_unexpected_error_returns_500_without_internal_details(monkeypatch):
    def fail_ranking(*_args, **_kwargs):
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr(app_module, "rank_recipes", fail_ranking)
    safe_client = TestClient(app_module.app, raise_server_exceptions=False)

    response = safe_client.post("/v1/meal-rankings", json=VALID_REQUEST)

    assert response.status_code == 500
    assert "private implementation detail" not in response.text


def test_identical_http_requests_return_identical_ordered_responses():
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
def test_meal_rankings_rejects_invalid_numeric_boundaries(field, value):
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
def test_meal_rankings_rejects_wrong_numeric_types(field, value):
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, field: value},
    )

    assert response.status_code == 422
    assert field in response.text


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_meal_rankings_rejects_non_finite_protein_target(value):
    response = safe_client.post(
        "/v1/meal-rankings",
        content=json.dumps({**VALID_REQUEST, "min_protein_g": value}),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert "min_protein_g" in response.text


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
    request_update, expected_field
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
def test_meal_rankings_rejects_blank_ingredient_values(field, value):
    response = safe_client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, field: value},
    )

    assert response.status_code == 422
    assert field in response.text


def test_meal_rankings_rejects_unknown_request_fields():
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, "ranking_model": "future"},
    )

    assert response.status_code == 422
    assert "ranking_model" in response.text
