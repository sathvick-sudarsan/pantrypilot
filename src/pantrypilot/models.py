from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StrictInt,
    field_validator,
)

from pantrypilot.normalization import normalize_ingredients


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    required_ingredients: tuple[str, ...] = Field(min_length=1)
    calories: int | FiniteFloat = Field(ge=0)
    protein_g: FiniteFloat = Field(ge=0)
    prep_minutes: StrictInt = Field(ge=0)

    @field_validator("id", "name")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("recipe text values must not be blank")
        return value

    @field_validator("calories", "protein_g", mode="before")
    @classmethod
    def reject_non_numeric_nutrition(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("nutrition values must be numbers")
        return value

    @field_validator("required_ingredients")
    @classmethod
    def normalize_required_ingredients(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_ingredients(values)


class ScoreComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: float
    weight: float
    contribution: float


class ScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pantry_coverage: ScoreComponent
    protein_fit: ScoreComponent
    time_fit: ScoreComponent
