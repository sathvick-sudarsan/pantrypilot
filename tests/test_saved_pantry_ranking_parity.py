import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from pantrypilot.app import create_app
from pantrypilot.catalog_store import initialize_catalog
from pantrypilot.ingredients import INGREDIENT_REGISTRY

CONSTRAINTS = {
    "min_protein_g": 20.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": [],
    "limit": 50,
}


def assert_complete_parity(
    client: TestClient,
    canonical_names: list[str],
    constraints: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    inline = client.post(
        "/v1/meal-rankings",
        json={"pantry_items": canonical_names, **constraints},
    )
    saved = client.post(
        "/v1/saved-pantry/meal-rankings",
        json=constraints,
    )

    assert saved.status_code == inline.status_code
    assert saved.json() == inline.json()
    return saved.json(), inline.json()


def test_aliases_and_duplicates_canonicalize_to_complete_ranking_parity(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(tmp_path / "pantrypilot.sqlite3")) as client:
        saved = client.put(
            "/v1/saved-pantry",
            json={
                "pantry_items": [
                    "black bean",
                    "Black Beans",
                    "egg",
                    "eggs",
                    "olive oil",
                ]
            },
        )
        canonical_names = [
            item["canonical_name"] for item in saved.json()["pantry_items"]
        ]

        body, _ = assert_complete_parity(client, canonical_names, CONSTRAINTS)

    assert saved.json()["pantry_items"] == [
        {"ingredient_id": "black-beans", "canonical_name": "black beans"},
        {"ingredient_id": "eggs", "canonical_name": "eggs"},
        {"ingredient_id": "olive-oil", "canonical_name": "olive oil"},
    ]
    assert body["returned_count"] == len(body["results"])
    assert len(body["results"]) > 1


def test_established_empty_pantry_has_complete_zero_coverage_parity(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(tmp_path / "pantrypilot.sqlite3")) as client:
        assert (
            client.put("/v1/saved-pantry", json={"pantry_items": []}).status_code == 200
        )

        body, _ = assert_complete_parity(client, [], CONSTRAINTS)

    assert all(
        result["score_breakdown"]["pantry_coverage"]["value"] == 0.0
        for result in body["results"]
    )


def test_unresolved_exclusion_has_complete_fail_closed_parity(tmp_path: Path) -> None:
    constraints = {**CONSTRAINTS, "excluded_ingredients": ["groundnut"]}
    with TestClient(create_app(tmp_path / "pantrypilot.sqlite3")) as client:
        assert (
            client.put("/v1/saved-pantry", json={"pantry_items": ["egg"]}).status_code
            == 200
        )

        saved, inline = assert_complete_parity(client, ["eggs"], constraints)

    assert saved == inline
    assert saved["detail"]["type"] == "unresolved_excluded_ingredients"


def test_physical_pantry_row_order_cannot_change_complete_ranking(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with TestClient(create_app(database_path)) as client:
        assert (
            client.put(
                "/v1/saved-pantry",
                json={"pantry_items": ["black beans", "eggs", "spinach"]},
            ).status_code
            == 200
        )
        with sqlite3.connect(database_path) as connection:
            connection.execute("DELETE FROM saved_pantry_items")
            connection.executemany(
                "INSERT INTO saved_pantry_items VALUES (1, ?)",
                [("spinach",), ("eggs",), ("black-beans",)],
            )

        assert_complete_parity(
            client,
            ["black beans", "eggs", "spinach"],
            CONSTRAINTS,
        )


def test_saved_ranking_preserves_recipe_id_tie_break_limit_and_count(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ties.sqlite3"
    tied_records = (
        {
            "id": "z-recipe",
            "name": "Z Recipe",
            "required_ingredient_ids": ["eggs"],
            "calories": 200,
            "protein_g": 20.0,
            "prep_minutes": 10,
        },
        {
            "id": "a-recipe",
            "name": "A Recipe",
            "required_ingredient_ids": ["eggs"],
            "calories": 200,
            "protein_g": 20.0,
            "prep_minutes": 10,
        },
    )
    initialize_catalog(database_path, tied_records, INGREDIENT_REGISTRY)
    constraints = {**CONSTRAINTS, "min_protein_g": 20.0, "limit": 1}

    with TestClient(create_app(database_path)) as client:
        assert (
            client.put("/v1/saved-pantry", json={"pantry_items": ["egg"]}).status_code
            == 200
        )

        body, _ = assert_complete_parity(client, ["eggs"], constraints)

    assert [result["id"] for result in body["results"]] == ["a-recipe"]
    assert body["returned_count"] == 1
    result = body["results"][0]
    assert result["final_score"] == round(
        sum(
            component["contribution"]
            for component in result["score_breakdown"].values()
        ),
        4,
    )
    assert result["explanation"]
