from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pantrypilot.normalization import normalize_ingredient

INGREDIENT_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
IngredientMatchType = Literal["canonical", "alias", "unresolved"]


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


class IngredientResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input: str
    normalized: str
    ingredient_id: str | None
    canonical_name: str | None
    match_type: IngredientMatchType

    @model_validator(mode="after")
    def validate_resolution_state(self) -> "IngredientResolution":
        has_identity = (
            self.ingredient_id is not None and self.canonical_name is not None
        )
        if self.match_type == "unresolved" and (
            self.ingredient_id is not None or self.canonical_name is not None
        ):
            raise ValueError("unresolved ingredients must not contain identity fields")
        if self.match_type != "unresolved" and not has_identity:
            raise ValueError("resolved ingredients require both identity fields")
        return self


class IngredientResolutionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pantry_items: tuple[IngredientResolution, ...]
    excluded_ingredients: tuple[IngredientResolution, ...]


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


def resolve_ingredient(
    value: str,
    registry: IngredientRegistry,
) -> IngredientResolution:
    normalized = normalize_ingredient(value)
    ingredient_id = registry.by_term.get(normalized)
    if ingredient_id is None:
        return IngredientResolution(
            input=value,
            normalized=normalized,
            ingredient_id=None,
            canonical_name=None,
            match_type="unresolved",
        )
    ingredient = registry.by_id[ingredient_id]
    if normalized != ingredient.canonical_name:
        return IngredientResolution(
            input=value,
            normalized=normalized,
            ingredient_id=ingredient.id,
            canonical_name=ingredient.canonical_name,
            match_type="alias",
        )
    return IngredientResolution(
        input=value,
        normalized=normalized,
        ingredient_id=ingredient.id,
        canonical_name=ingredient.canonical_name,
        match_type="canonical",
    )


def resolve_ingredients(
    values: Iterable[str],
    registry: IngredientRegistry,
) -> tuple[IngredientResolution, ...]:
    return tuple(resolve_ingredient(value, registry) for value in values)


RAW_INGREDIENTS = (
    {"id": "eggs", "canonical_name": "eggs", "aliases": ["egg"]},
    {"id": "spinach", "canonical_name": "spinach", "aliases": []},
    {"id": "olive-oil", "canonical_name": "olive oil", "aliases": []},
    {
        "id": "black-beans",
        "canonical_name": "black beans",
        "aliases": ["black bean"],
    },
    {
        "id": "corn-tortillas",
        "canonical_name": "corn tortillas",
        "aliases": ["corn tortilla"],
    },
    {"id": "avocado", "canonical_name": "avocado", "aliases": []},
    {"id": "lime", "canonical_name": "lime", "aliases": []},
    {"id": "noodles", "canonical_name": "noodles", "aliases": []},
    {"id": "peanuts", "canonical_name": "peanuts", "aliases": ["peanut"]},
    {"id": "soy-sauce", "canonical_name": "soy sauce", "aliases": []},
    {"id": "lentils", "canonical_name": "lentils", "aliases": ["lentil"]},
    {"id": "carrots", "canonical_name": "carrots", "aliases": ["carrot"]},
    {"id": "celery", "canonical_name": "celery", "aliases": []},
    {
        "id": "vegetable-broth",
        "canonical_name": "vegetable broth",
        "aliases": ["vegetable stock"],
    },
)

INGREDIENT_REGISTRY = load_ingredient_registry(RAW_INGREDIENTS)
