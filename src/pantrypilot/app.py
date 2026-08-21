import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from math import isfinite
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pantrypilot.catalog import INITIAL_RECIPE_CATALOG
from pantrypilot.catalog_store import initialize_catalog, load_durable_catalog
from pantrypilot.ingredients import INGREDIENT_REGISTRY, resolve_ingredients
from pantrypilot.models import (
    RankingRequest,
    RankingResponse,
    SavedPantryItem,
    SavedPantryRankingRequest,
    SavedPantryResponse,
    SavedPantryWriteRequest,
)
from pantrypilot.pantry_store import (
    PantryStoreError,
    load_saved_pantry,
    replace_saved_pantry,
)
from pantrypilot.ranking import UnresolvedExcludedIngredientsError, rank_recipes

DATABASE_PATH_ENV = "PANTRYPILOT_DB_PATH"
DEFAULT_DATABASE_PATH = Path("pantrypilot.sqlite3")


def _replace_non_finite_values(value: object) -> object:
    if isinstance(value, float) and not isfinite(value):
        if value != value:
            return "NaN"
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {key: _replace_non_finite_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_non_finite_values(item) for item in value]
    return value


def create_app(database_path: Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        initialize_catalog(
            database_path,
            INITIAL_RECIPE_CATALOG,
            INGREDIENT_REGISTRY,
        )
        application.state.recipe_catalog = load_durable_catalog(
            database_path,
            INGREDIENT_REGISTRY,
        )
        yield

    application = FastAPI(title="PantryPilot", lifespan=lifespan)

    def saved_pantry_response(
        ingredient_ids: tuple[str, ...],
    ) -> SavedPantryResponse:
        return SavedPantryResponse(
            pantry_items=tuple(
                SavedPantryItem(
                    ingredient_id=ingredient_id,
                    canonical_name=(
                        INGREDIENT_REGISTRY.by_id[ingredient_id].canonical_name
                    ),
                )
                for ingredient_id in ingredient_ids
            )
        )

    def required_saved_pantry() -> tuple[str, ...]:
        ingredient_ids = load_saved_pantry(database_path, INGREDIENT_REGISTRY)
        if ingredient_ids is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "saved_pantry_not_found",
                    "message": "No saved pantry has been established.",
                },
            )
        return ingredient_ids

    def rank_or_422(ranking_request: RankingRequest) -> RankingResponse:
        try:
            return rank_recipes(
                ranking_request,
                application.state.recipe_catalog,
                INGREDIENT_REGISTRY,
            )
        except UnresolvedExcludedIngredientsError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "unresolved_excluded_ingredients",
                    "message": "All excluded ingredients must resolve before ranking.",
                    "ingredient_resolution": (
                        exc.ingredient_resolution.model_dump(mode="json")
                    ),
                },
            ) from exc

    @application.exception_handler(RequestValidationError)
    def request_validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        detail = _replace_non_finite_values(jsonable_encoder(exc.errors()))
        return JSONResponse(status_code=422, content={"detail": detail})

    @application.exception_handler(PantryStoreError)
    def saved_pantry_exception_handler(
        _request: Request,
        _exc: PantryStoreError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "type": "saved_pantry_unavailable",
                    "message": "Saved pantry is unavailable.",
                }
            },
        )

    @application.post("/v1/meal-rankings", response_model=RankingResponse)
    def create_meal_ranking(
        ranking_request: RankingRequest,
    ) -> RankingResponse:
        return rank_or_422(ranking_request)

    @application.put("/v1/saved-pantry", response_model=SavedPantryResponse)
    def replace_saved_pantry_route(
        request: SavedPantryWriteRequest,
    ) -> SavedPantryResponse:
        resolutions = resolve_ingredients(request.pantry_items, INGREDIENT_REGISTRY)
        if any(resolution.ingredient_id is None for resolution in resolutions):
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "unresolved_pantry_items",
                    "message": "All pantry items must resolve before saving.",
                    "ingredient_resolution": {
                        "pantry_items": [
                            resolution.model_dump(mode="json")
                            for resolution in resolutions
                        ]
                    },
                },
            )
        canonical_ids = tuple(
            sorted(
                {
                    resolution.ingredient_id
                    for resolution in resolutions
                    if resolution.ingredient_id is not None
                }
            )
        )
        saved_ids = replace_saved_pantry(
            database_path,
            canonical_ids,
            INGREDIENT_REGISTRY,
        )
        return saved_pantry_response(saved_ids)

    @application.get("/v1/saved-pantry", response_model=SavedPantryResponse)
    def get_saved_pantry() -> SavedPantryResponse:
        return saved_pantry_response(required_saved_pantry())

    @application.post(
        "/v1/saved-pantry/meal-rankings",
        response_model=RankingResponse,
    )
    def create_saved_pantry_meal_ranking(
        request: SavedPantryRankingRequest,
    ) -> RankingResponse:
        canonical_names = [
            INGREDIENT_REGISTRY.by_id[ingredient_id].canonical_name
            for ingredient_id in required_saved_pantry()
        ]
        ranking_request = RankingRequest(
            pantry_items=canonical_names,
            **request.model_dump(),
        )
        return rank_or_422(ranking_request)

    return application


app = create_app(Path(os.environ.get(DATABASE_PATH_ENV, str(DEFAULT_DATABASE_PATH))))
