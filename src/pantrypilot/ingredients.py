from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pantrypilot.normalization import normalize_ingredient

INGREDIENT_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class CanonicalIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=INGREDIENT_ID_PATTERN)
    canonical_name: str
    aliases: tuple[str, ...]

    @field_validator("canonical_name")
    @classmethod
    def normalize_canonical_name(cls, value: str) -> str:
        return normalize_ingredient(value)

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            alias = normalize_ingredient(value)
            if alias in seen:
                raise ValueError(f"duplicate ingredient alias: {alias}")
            seen.add(alias)
            normalized.append(alias)
        return tuple(normalized)

    @model_validator(mode="after")
    def reject_canonical_name_alias(self) -> "CanonicalIngredient":
        if self.canonical_name in self.aliases:
            raise ValueError(
                f"ingredient alias duplicates canonical name: {self.canonical_name}"
            )
        return self


@dataclass(frozen=True)
class IngredientRegistry:
    by_id: Mapping[str, CanonicalIngredient]
    by_term: Mapping[str, str]


def load_ingredient_registry(
    records: Iterable[Mapping[str, object]],
) -> IngredientRegistry:
    by_id: dict[str, CanonicalIngredient] = {}
    by_term: dict[str, str] = {}
    for record in records:
        ingredient = CanonicalIngredient.model_validate(record)
        if ingredient.id in by_id:
            raise ValueError(f"duplicate ingredient id: {ingredient.id}")
        for term in (ingredient.canonical_name, *ingredient.aliases):
            existing_id = by_term.get(term)
            if existing_id is not None:
                raise ValueError(
                    f"ingredient term '{term}' maps to both "
                    f"'{existing_id}' and '{ingredient.id}'"
                )
            by_term[term] = ingredient.id
        by_id[ingredient.id] = ingredient
    return IngredientRegistry(
        by_id=MappingProxyType(by_id),
        by_term=MappingProxyType(by_term),
    )
