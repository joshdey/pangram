from typing import Any, Protocol, Self

from pangram import Pangram

from pangram_slack.types.pangram import PangramAnalysisRequest, PangramAnalysisResponse


class PangramSDK(Protocol):
    """The Pangram SDK methods used by this application."""

    def predict(
        self,
        text: str,
        *,
        model: str,
        public_dashboard_link: bool,
    ) -> dict[str, Any]: ...


class PangramClient:
    """Typed client boundary for the Pangram API."""

    def __init__(self, client: PangramSDK) -> None:
        self._client = client

    def analyze(self, request: PangramAnalysisRequest) -> PangramAnalysisResponse:
        """Analyze text for AI-generated and AI-assisted content."""
        response = self._client.predict(
            request.text,
            model=request.model,
            public_dashboard_link=request.include_dashboard_link,
        )
        analysis = PangramAnalysisResponse.model_validate(response)
        return analysis

    @classmethod
    def default(cls, api_key: str) -> Self:
        """Create a client backed by the official Pangram SDK."""
        return cls(client=Pangram(api_key=api_key))
