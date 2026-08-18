import pytest
from pydantic import ValidationError

from pantrypilot.models import SavedPantryRankingRequest, SavedPantryWriteRequest

VALID_SAVED_RANKING = {
    "min_protein_g": 25.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": ["peanuts"],
    "limit": 10,
}


def test_saved_ranking_accepts_exact_existing_constraints_without_pantry_items() -> (
    None
):
    request = SavedPantryRankingRequest(**VALID_SAVED_RANKING)

    assert request.model_dump() == VALID_SAVED_RANKING


@pytest.mark.parametrize(
    "body",
    [
        {**VALID_SAVED_RANKING, "pantry_items": ["eggs"]},
        {**VALID_SAVED_RANKING, "pantry_source": "saved"},
    ],
)
def test_saved_ranking_rejects_mode_and_inline_pantry_fields(
    body: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SavedPantryRankingRequest(**body)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_protein_g", -0.1),
        ("max_prep_minutes", -1),
        ("max_prep_minutes", 10.5),
        ("limit", 0),
        ("limit", 51),
        ("excluded_ingredients", [" "]),
    ],
)
def test_saved_ranking_reuses_existing_constraint_boundaries(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        SavedPantryRankingRequest(**{**VALID_SAVED_RANKING, field: value})


@pytest.mark.parametrize("count", [0, 100])
def test_saved_pantry_write_accepts_zero_and_one_hundred_items(count: int) -> None:
    request = SavedPantryWriteRequest(
        pantry_items=[f"item-{index}" for index in range(count)]
    )
    assert len(request.pantry_items) == count


def test_saved_pantry_write_rejects_one_hundred_one_items() -> None:
    with pytest.raises(ValidationError):
        SavedPantryWriteRequest(pantry_items=[f"item-{index}" for index in range(101)])


def test_saved_pantry_write_accepts_one_hundred_character_nonblank_item() -> None:
    value = "x" * 100
    assert SavedPantryWriteRequest(pantry_items=[value]).pantry_items == [value]


def test_saved_pantry_write_rejects_item_over_one_hundred_characters() -> None:
    with pytest.raises(ValidationError):
        SavedPantryWriteRequest(pantry_items=["x" * 101])


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_saved_pantry_write_rejects_blank_item(value: str) -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        SavedPantryWriteRequest(pantry_items=[value])


def test_saved_pantry_write_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SavedPantryWriteRequest(pantry_items=[], owner="future-user")
