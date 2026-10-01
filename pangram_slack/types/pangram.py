from pydantic import BaseModel, ConfigDict


class PangramAnalysisRequest(BaseModel):
    """Input for a Pangram text analysis."""

    include_dashboard_link: bool
    model: str
    text: str


class PangramAnalysisResponse(BaseModel):
    """Pangram fields presented back to the Slack user."""

    model_config = ConfigDict(extra="ignore")

    dashboard_link: str | None = None
    fraction_ai: float
    fraction_ai_assisted: float
    fraction_human: float
    prediction: str
    prediction_short: str

    @property
    def contains_ai(self) -> bool:
        """Return whether Pangram found any AI-written or AI-assisted text."""
        return self.fraction_ai > 0 or self.fraction_ai_assisted > 0
