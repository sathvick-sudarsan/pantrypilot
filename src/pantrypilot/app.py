from math import isfinite

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pantrypilot.catalog import CATALOG
from pantrypilot.models import RankingRequest, RankingResponse
from pantrypilot.ranking import rank_recipes

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
    results = rank_recipes(request, CATALOG)
    return RankingResponse(results=results, returned_count=len(results))
