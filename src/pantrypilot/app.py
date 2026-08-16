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
from pantrypilot.ingredients import INGREDIENT_REGISTRY
from pantrypilot.models import RankingRequest, RankingResponse
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

    @application.exception_handler(RequestValidationError)
    def request_validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        detail = _replace_non_finite_values(jsonable_encoder(exc.errors()))
        return JSONResponse(status_code=422, content={"detail": detail})

    @application.post("/v1/meal-rankings", response_model=RankingResponse)
    def create_meal_ranking(
        ranking_request: RankingRequest,
        http_request: Request,
    ) -> RankingResponse:
        try:
            return rank_recipes(
                ranking_request,
                http_request.app.state.recipe_catalog,
                INGREDIENT_REGISTRY,
            )
        except UnresolvedExcludedIngredientsError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "unresolved_excluded_ingredients",
                    "message": (
                        "All excluded ingredients must resolve before ranking."
                    ),
                    "ingredient_resolution": (
                        exc.ingredient_resolution.model_dump(mode="json")
                    ),
                },
            ) from exc

    return application


app = create_app(Path(os.environ.get(DATABASE_PATH_ENV, str(DEFAULT_DATABASE_PATH))))
