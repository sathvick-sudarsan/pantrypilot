from math import isfinite

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pantrypilot.catalog import CATALOG
from pantrypilot.ingredients import INGREDIENT_REGISTRY
from pantrypilot.models import RankingRequest, RankingResponse
from pantrypilot.ranking import UnresolvedExcludedIngredientsError, rank_recipes

app = FastAPI(title="PantryPilot")


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


@app.exception_handler(RequestValidationError)
def request_validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    detail = _replace_non_finite_values(jsonable_encoder(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": detail})


@app.post("/v1/meal-rankings", response_model=RankingResponse)
def create_meal_ranking(request: RankingRequest) -> RankingResponse:
    try:
        return rank_recipes(request, CATALOG, INGREDIENT_REGISTRY)
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
