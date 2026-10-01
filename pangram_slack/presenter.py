from pangram_slack.types.pangram import PangramAnalysisResponse


def format_analysis(
    analysis: PangramAnalysisResponse,
    source_permalink: str | None,
) -> str:
    """Format a Pangram response for Slack."""
    source = f"\n<{source_permalink}|View analyzed message>" if source_permalink else ""
    dashboard = (
        f" · <{analysis.dashboard_link}|Open Pangram report>"
        if analysis.dashboard_link
        else ""
    )

    return (
        f"*Pangram result: {analysis.prediction_short}*\n"
        f"{analysis.prediction}\n"
        f"AI-written: *{analysis.fraction_ai:.0%}* · "
        f"AI-assisted: *{analysis.fraction_ai_assisted:.0%}* · "
        f"Human: *{analysis.fraction_human:.0%}*{source}{dashboard}"
    )
