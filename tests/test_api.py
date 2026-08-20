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
from pantrypilot.pantry_store import PantryStoreError


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

SAVED_RANKING_REQUEST = {
    "min_protein_g": 0.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": [],
    "limit": 50,
}


def test_lifespan_initializes_and_publishes_frozen_catalog(tmp_path: Path) -> None:
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


def test_exported_app_uses_configured_database_path_during_lifespan(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "configured.sqlite3"
    environment = os.environ.copy()
    environment["PANTRYPILOT_DB_PATH"] = str(database_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from fastapi.testclient import TestClient\n"
                "from pantrypilot.app import app\n"
                "with TestClient(app):\n"
                "    pass\n"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert database_path.exists()


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
        connection.execute("PRAGMA user_version = 2")

    with pytest.raises(CatalogStoreError):
        with TestClient(create_app(database_path)):
            pass


def test_request_uses_snapshot_without_database_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = create_app(tmp_path / "catalog.sqlite3")
    with TestClient(application) as client:

        def fail_if_called(*args: object, **kwargs: object) -> sqlite3.Connection:
            raise AssertionError("request attempted database I/O")

        monkeypatch.setattr(sqlite3, "connect", fail_if_called)

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


def test_get_saved_pantry_returns_exact_absent_404(client: TestClient) -> None:
    response = client.get("/v1/saved-pantry")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "type": "saved_pantry_not_found",
            "message": "No saved pantry has been established.",
        }
    }


def test_put_establishes_empty_saved_pantry(client: TestClient) -> None:
    put_response = client.put("/v1/saved-pantry", json={"pantry_items": []})
    get_response = client.get("/v1/saved-pantry")

    assert put_response.status_code == get_response.status_code == 200
    assert put_response.json() == get_response.json() == {"pantry_items": []}


def test_saved_pantry_put_accepts_one_hundred_occurrences_and_deduplicates(
    client: TestClient,
) -> None:
    response = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": ["eggs"] * 100},
    )

    assert response.status_code == 200
    assert response.json() == {
        "pantry_items": [{"ingredient_id": "eggs", "canonical_name": "eggs"}]
    }


def test_saved_pantry_put_accepts_one_hundred_characters_before_resolution(
    client: TestClient,
) -> None:
    pantry_item = "x" * 100

    response = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": [pantry_item]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "unresolved_pantry_items"
    assert (
        response.json()["detail"]["ingredient_resolution"]["pantry_items"][0]["input"]
        == pantry_item
    )


@pytest.mark.parametrize(
    "pantry_items",
    [
        ["eggs"] * 101,
        ["x" * 101],
        ["   "],
    ],
    ids=("one-hundred-one-occurrences", "one-hundred-one-characters", "blank"),
)
def test_saved_pantry_put_rejects_invalid_bounds_before_mutation(
    client: TestClient,
    pantry_items: list[str],
) -> None:
    established = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": ["spinach"]},
    )

    response = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": pantry_items},
    )

    assert established.status_code == 200
    assert response.status_code == 422
    assert "unresolved_pantry_items" not in response.text
    assert client.get("/v1/saved-pantry").json() == {
        "pantry_items": [{"ingredient_id": "spinach", "canonical_name": "spinach"}]
    }


def test_put_resolves_deduplicates_replaces_and_orders_canonical_items(
    client: TestClient,
) -> None:
    first = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": ["spinach", "egg", "Eggs", "spinach"]},
    )
    second = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": ["black bean", "olive oil"]},
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == {
        "pantry_items": [
            {"ingredient_id": "eggs", "canonical_name": "eggs"},
            {"ingredient_id": "spinach", "canonical_name": "spinach"},
        ]
    }
    assert second.json() == {
        "pantry_items": [
            {"ingredient_id": "black-beans", "canonical_name": "black beans"},
            {"ingredient_id": "olive-oil", "canonical_name": "olive oil"},
        ]
    }
    assert client.get("/v1/saved-pantry").json() == second.json()


def test_equivalent_puts_are_idempotent_by_canonical_id_set(client: TestClient) -> None:
    first = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": ["egg", "spinach", "egg"]},
    )
    second = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": ["spinach", "eggs"]},
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_unresolved_put_returns_all_occurrences_in_order_without_store_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with TestClient(create_app(database_path)) as client:
        established = client.put(
            "/v1/saved-pantry",
            json={"pantry_items": ["eggs"]},
        )
        assert established.status_code == 200
        calls = 0

        def forbidden_store_call(*_args: object, **_kwargs: object) -> tuple[str, ...]:
            nonlocal calls
            calls += 1
            raise AssertionError("unresolved replacement reached storage")

        monkeypatch.setattr(app_module, "replace_saved_pantry", forbidden_store_call)
        response = client.put(
            "/v1/saved-pantry",
            json={"pantry_items": ["egg", "mystery", "eggs", "unknown"]},
        )

        assert response.status_code == 422
        assert response.json() == {
            "detail": {
                "type": "unresolved_pantry_items",
                "message": "All pantry items must resolve before saving.",
                "ingredient_resolution": {
                    "pantry_items": [
                        {
                            "input": "egg",
                            "normalized": "egg",
                            "ingredient_id": "eggs",
                            "canonical_name": "eggs",
                            "match_type": "alias",
                        },
                        {
                            "input": "mystery",
                            "normalized": "mystery",
                            "ingredient_id": None,
                            "canonical_name": None,
                            "match_type": "unresolved",
                        },
                        {
                            "input": "eggs",
                            "normalized": "eggs",
                            "ingredient_id": "eggs",
                            "canonical_name": "eggs",
                            "match_type": "canonical",
                        },
                        {
                            "input": "unknown",
                            "normalized": "unknown",
                            "ingredient_id": None,
                            "canonical_name": None,
                            "match_type": "unresolved",
                        },
                    ]
                },
            }
        }
        assert calls == 0

    with TestClient(create_app(database_path)) as restarted:
        assert restarted.get("/v1/saved-pantry").json() == {
            "pantry_items": [{"ingredient_id": "eggs", "canonical_name": "eggs"}]
        }


def test_known_saved_pantry_failure_returns_safe_exact_503(
    safe_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_read(*_args: object, **_kwargs: object) -> None:
        raise PantryStoreError("C:\\private\\pantry.sqlite3: SQL secret")

    monkeypatch.setattr(app_module, "load_saved_pantry", fail_read)

    response = safe_client.get("/v1/saved-pantry")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "type": "saved_pantry_unavailable",
            "message": "Saved pantry is unavailable.",
        }
    }
    assert "private" not in response.text
    assert "SQL" not in response.text


def test_unexpected_saved_pantry_programming_error_remains_generic_500(
    safe_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def programming_error(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("private programmer defect")

    monkeypatch.setattr(app_module, "load_saved_pantry", programming_error)

    response = safe_client.get("/v1/saved-pantry")

    assert response.status_code == 500
    assert "saved_pantry_unavailable" not in response.text
    assert "private programmer defect" not in response.text


@pytest.mark.parametrize(
    "body",
    [{}, {"pantry_items": [], "owner": "future-user"}],
)
def test_put_saved_pantry_rejects_invalid_request_shape(
    client: TestClient,
    body: dict[str, object],
) -> None:
    assert client.put("/v1/saved-pantry", json=body).status_code == 422


def test_saved_pantry_survives_application_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with TestClient(create_app(database_path)) as first:
        assert (
            first.put(
                "/v1/saved-pantry",
                json={"pantry_items": ["spinach", "egg"]},
            ).status_code
            == 200
        )

    with TestClient(create_app(database_path)) as restarted:
        assert restarted.get("/v1/saved-pantry").json() == {
            "pantry_items": [
                {"ingredient_id": "eggs", "canonical_name": "eggs"},
                {"ingredient_id": "spinach", "canonical_name": "spinach"},
            ]
        }


def test_corrupt_saved_pantry_does_not_block_inline_ranking_after_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with TestClient(create_app(database_path)):
        pass
    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO saved_pantry_items VALUES (1, 'eggs')")

    with TestClient(create_app(database_path), raise_server_exceptions=False) as client:
        replacement = client.put(
            "/v1/saved-pantry",
            json={"pantry_items": ["spinach"]},
        )
        inline = client.post("/v1/meal-rankings", json=VALID_REQUEST)
        saved_get = client.get("/v1/saved-pantry")
        saved_ranking = client.post(
            "/v1/saved-pantry/meal-rankings",
            json=SAVED_RANKING_REQUEST,
        )

    assert inline.status_code == 200
    assert (
        replacement.status_code
        == saved_get.status_code
        == saved_ranking.status_code
        == 503
    )
    assert (
        replacement.json()
        == saved_get.json()
        == saved_ranking.json()
        == {
            "detail": {
                "type": "saved_pantry_unavailable",
                "message": "Saved pantry is unavailable.",
            }
        }
    )
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT id FROM saved_pantry").fetchall() == []
        assert connection.execute(
            "SELECT pantry_id, ingredient_id FROM saved_pantry_items "
            "ORDER BY ingredient_id"
        ).fetchall() == [(1, "eggs")]


def test_saved_ranking_returns_same_exact_absent_404(client: TestClient) -> None:
    response = client.post(
        "/v1/saved-pantry/meal-rankings",
        json=SAVED_RANKING_REQUEST,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "type": "saved_pantry_not_found",
            "message": "No saved pantry has been established.",
        }
    }


def test_saved_ranking_accepts_established_empty_pantry(client: TestClient) -> None:
    assert client.put("/v1/saved-pantry", json={"pantry_items": []}).status_code == 200

    response = client.post(
        "/v1/saved-pantry/meal-rankings",
        json=SAVED_RANKING_REQUEST,
    )

    assert response.status_code == 200
    assert response.json()["returned_count"] > 0
    assert all(
        result["score_breakdown"]["pantry_coverage"]["value"] == 0.0
        for result in response.json()["results"]
    )


def test_saved_ranking_rejects_pantry_items_and_inline_omission_stays_invalid(
    client: TestClient,
) -> None:
    assert (
        client.post(
            "/v1/saved-pantry/meal-rankings",
            json={**SAVED_RANKING_REQUEST, "pantry_items": ["eggs"]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/meal-rankings",
            json=SAVED_RANKING_REQUEST,
        ).status_code
        == 422
    )


def test_saved_ranking_preserves_fail_closed_unresolved_exclusions(
    client: TestClient,
) -> None:
    assert (
        client.put("/v1/saved-pantry", json={"pantry_items": ["eggs"]}).status_code
        == 200
    )

    response = client.post(
        "/v1/saved-pantry/meal-rankings",
        json={**SAVED_RANKING_REQUEST, "excluded_ingredients": ["groundnut"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "unresolved_excluded_ingredients"
    assert (
        response.json()["detail"]["ingredient_resolution"]["excluded_ingredients"][0][
            "input"
        ]
        == "groundnut"
    )


def test_saved_ranking_maps_pantry_store_error_to_exact_safe_503(
    safe_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_read(*_args: object, **_kwargs: object) -> None:
        raise PantryStoreError("C:\\private\\pantry.sqlite3: SQL secret")

    monkeypatch.setattr(app_module, "load_saved_pantry", fail_read)

    response = safe_client.post(
        "/v1/saved-pantry/meal-rankings",
        json=SAVED_RANKING_REQUEST,
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "type": "saved_pantry_unavailable",
            "message": "Saved pantry is unavailable.",
        }
    }
    assert "private" not in response.text
    assert "SQL" not in response.text
