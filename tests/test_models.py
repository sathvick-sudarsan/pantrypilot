import pytest
from pydantic import ValidationError

from pantrypilot.models import SavedPantryWriteRequest


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
