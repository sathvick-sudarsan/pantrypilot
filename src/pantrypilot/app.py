from fastapi import FastAPI

from pantrypilot.catalog import CATALOG
from pantrypilot.models import RankingRequest, RankingResponse
from pantrypilot.ranking import rank_recipes

app = FastAPI(title="PantryPilot")


@app.post("/v1/meal-rankings", response_model=RankingResponse)
def create_meal_ranking(request: RankingRequest) -> RankingResponse:
    results = rank_recipes(request, CATALOG)
    return RankingResponse(results=results, returned_count=len(results))
