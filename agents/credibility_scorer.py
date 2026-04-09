import json
import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from pipeline.state import EarningsState


load_dotenv()
logger = logging.getLogger(__name__)


def _strip_json_fences(raw: str) -> str:
    """Remove markdown code fences around JSON if present.

    Args:
        raw: Raw model output text.

    Returns:
        Cleaned text likely to be valid JSON.

    Raises:
        None.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def score_credibility(state: EarningsState) -> dict:
    """LangGraph node — Agent 4: cross-validates guidance vs actuals.

    Scores credibility 0-100, detects language drift, and sets route.

    Args:
        state: Earnings pipeline state after guidance and actual extraction.

    Returns:
        Updated state fields for credibility scoring.

    Raises:
        None.
    """
    if state.get("input_valid") is False:
        return {"errors": state.get("errors", [])}

    guidance_items = state.get("guidance_items", [])
    if not guidance_items:
        return {
            "credibility_score": 0.0,
            "credibility_breakdown": [],
            "language_drift_flags": [],
            "route": "red_flag",
            "errors": state.get("errors", []) + ["No guidance items to score"],
        }

    prompt_path = os.path.join(os.getcwd(), "prompts", "credibility_scorer.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        template = f.read()

    prompt = (
        template.replace("{guidance_items}", json.dumps(guidance_items, indent=2))
        .replace("{actual_items}", json.dumps(state.get("actual_items", []), indent=2))
        .replace("{prior_transcript}", state.get("prior_transcript", "")[:3000])
    )

    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        response = llm.invoke(prompt)
        raw = str(response.content).strip()
    except Exception as exc:
        logger.exception("Credibility scoring LLM call failed: %s", exc)
        return {
            "credibility_score": 0.0,
            "credibility_breakdown": [],
            "language_drift_flags": [],
            "route": "red_flag",
            "errors": state.get("errors", []) + ["Credibility scoring LLM call failed"],
        }

    try:
        parsed = json.loads(_strip_json_fences(raw))
    except json.JSONDecodeError:
        logger.error("Credibility scoring JSON parse error.")
        return {
            "credibility_score": 0.0,
            "credibility_breakdown": [],
            "language_drift_flags": [],
            "route": "red_flag",
            "errors": state.get("errors", []) + ["Credibility scoring JSON parse error"],
        }

    breakdown = parsed.get("breakdown", []) if isinstance(parsed, dict) else []
    language_drift_flags = (
        parsed.get("language_drift_flags", []) if isinstance(parsed, dict) else []
    )

    if not isinstance(breakdown, list) or len(breakdown) == 0:
        return {
            "credibility_score": 0.0,
            "credibility_breakdown": [],
            "language_drift_flags": language_drift_flags
            if isinstance(language_drift_flags, list)
            else [],
            "route": "red_flag",
            "errors": state.get("errors", [])
            + ["Credibility scoring produced empty breakdown"],
        }

    weights = {"DELIVERED": 1.0, "PARTIAL": 0.5, "MISSED": 0.0}
    score = round(
        sum(weights.get(str(item.get("verdict", "")), 0) for item in breakdown)
        / len(breakdown)
        * 100,
        1,
    )
    route = "red_flag" if score < 50 else "clean_bill"

    return {
        "credibility_score": score,
        "credibility_breakdown": breakdown,
        "language_drift_flags": language_drift_flags
        if isinstance(language_drift_flags, list)
        else [],
        "route": route,
    }
