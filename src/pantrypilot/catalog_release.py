import hashlib
import json
import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass

from pantrypilot.ingredients import IngredientRegistry
from pantrypilot.models import Recipe

RECIPE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RELEASE_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class CatalogRelease:
    version: int
    manifest_digest: str
    recipes: tuple[Recipe, ...]
    retired_recipe_ids: tuple[str, ...]


def canonical_manifest_bytes(
    recipes: Sequence[Recipe],
    retired_recipe_ids: Collection[str],
) -> bytes:
    payload = {
        "recipes": [
            {
                "id": recipe.id,
                "name": recipe.name,
                "calories": recipe.calories,
                "protein_g": recipe.protein_g,
                "prep_minutes": recipe.prep_minutes,
                "required_ingredient_ids": list(recipe.required_ingredient_ids),
            }
            for recipe in sorted(recipes, key=lambda recipe: recipe.id)
        ],
        "retired_official_recipe_ids": sorted(retired_recipe_ids),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def catalog_manifest_digest(
    recipes: Sequence[Recipe],
    retired_recipe_ids: Collection[str],
) -> str:
    return hashlib.sha256(
        canonical_manifest_bytes(recipes, retired_recipe_ids)
    ).hexdigest()


def build_catalog_release(
    recipes: Iterable[Recipe],
    retired_recipe_ids: Iterable[str],
    ingredient_registry: IngredientRegistry,
    current_version: int,
    release_digests: Mapping[int, str],
) -> CatalogRelease:
    if (
        isinstance(current_version, bool)
        or not isinstance(current_version, int)
        or current_version <= 0
    ):
        raise ValueError("current version must be positive")

    current_recipes = tuple(sorted(recipes, key=lambda recipe: recipe.id))
    current_ids = tuple(recipe.id for recipe in current_recipes)
    for recipe_id in current_ids:
        if RECIPE_ID_PATTERN.fullmatch(recipe_id) is None:
            raise ValueError("official recipe id must be lowercase kebab-case")
    if len(set(current_ids)) != len(current_ids):
        raise ValueError("duplicate current recipe id")

    retired_ids = tuple(retired_recipe_ids)
    for recipe_id in retired_ids:
        if RECIPE_ID_PATTERN.fullmatch(recipe_id) is None:
            raise ValueError("retired recipe id must be lowercase kebab-case")
    if len(set(retired_ids)) != len(retired_ids):
        raise ValueError("duplicate retired recipe id")
    retired_ids = tuple(sorted(retired_ids))
    if set(current_ids).intersection(retired_ids):
        raise ValueError("current and retired recipe id overlap")

    for recipe in current_recipes:
        for ingredient_id in recipe.required_ingredient_ids:
            if ingredient_id not in ingredient_registry.by_id:
                raise ValueError(
                    f"unknown ingredient id '{ingredient_id}' in recipe '{recipe.id}'"
                )

    expected_versions = set(range(1, current_version + 1))
    actual_versions = set(release_digests)
    if actual_versions != expected_versions or any(
        isinstance(version, bool) or not isinstance(version, int)
        for version in release_digests
    ):
        raise ValueError("release digest versions must be consecutive")
    for digest in release_digests.values():
        if (
            not isinstance(digest, str)
            or RELEASE_DIGEST_PATTERN.fullmatch(digest) is None
        ):
            raise ValueError("release ledger digest must be lowercase 64-hex")

    manifest_digest = catalog_manifest_digest(current_recipes, retired_ids)
    if release_digests[current_version] != manifest_digest:
        raise ValueError("current manifest digest does not match ledger")
    return CatalogRelease(
        version=current_version,
        manifest_digest=manifest_digest,
        recipes=current_recipes,
        retired_recipe_ids=retired_ids,
    )
