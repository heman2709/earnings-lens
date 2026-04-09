import json
import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from pipeline.state import EarningsState


load_dotenv()
logger = logging.getLogger(__name__)


def generate_report(state: EarningsState) -> dict:
    """LangGraph node — Agent 5: generates structured analyst brief.

    Uses route from state to select RED FLAG or CLEAN BILL template.
    Returns markdown report string.

    Args:
        state: Earnings pipeline state after credibility scoring.

    Returns:
        Dict containing generated markdown report text or errors.

    Raises:
        None.
    """
    if state.get("input_valid") is False:
        return {"errors": state.get("errors", [])}

    prompt_path = os.path.join(os.getcwd(), "prompts", "report_generator.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        template = f.read()

    prompt = (
        template.replace("{ticker}", state.get("ticker", ""))
        .replace("{quarter}", state.get("quarter", ""))
        .replace("{route}", state.get("route", "red_flag"))
        .replace("{credibility_score}", str(state.get("credibility_score", 0.0)))
        .replace(
            "{credibility_breakdown}",
            json.dumps(state.get("credibility_breakdown", []), indent=2),
        )
        .replace(
            "{language_drift_flags}",
            json.dumps(state.get("language_drift_flags", []), indent=2),
        )
    )

    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        response = llm.invoke(prompt)
        report = str(response.content).strip()
    except Exception as exc:
        logger.exception("Report generation LLM call failed: %s", exc)
        return {
            "report": "",
            "errors": state.get("errors", []) + ["Report generation LLM call failed"],
        }

    if not report:
        return {
            "report": "",
            "errors": state.get("errors", []) + ["Report generation returned empty text"],
        }

    return {"report": report}
