import json
import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from pipeline.state import EarningsState


logger = logging.getLogger(__name__)
load_dotenv()


def _strip_json_fences(raw: str) -> str:
    """Remove optional markdown code fences around JSON payloads.

    Args:
        raw: Raw model response content.

    Returns:
        Cleaned JSON string without surrounding markdown fences.

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


def extract_guidance(state: EarningsState) -> dict:
    """LangGraph node for structured prior-quarter guidance extraction.

    LangGraph node — Agent 2: extracts forward-looking guidance.
    Reads prior quarter transcript from state.
    Calls OpenAI to extract structured guidance items.
    Loads prompt from prompts/guidance_extractor.md.

    Args:
        state: EarningsState with prior_transcript populated.

    Returns:
        Dict with guidance_items list, or errors on failure.

    Raises:
        None.
    """
    if state.get("input_valid") is False:
        return {"errors": state.get("errors", [])}

    prompt_path = os.path.join(os.getcwd(), "prompts", "guidance_extractor.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        template = f.read()

    prompt = template.replace("{transcript}", state.get("prior_transcript", ""))

    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        response = llm.invoke(prompt)
        raw = str(response.content).strip()
    except Exception as exc:
        logger.exception("Guidance extraction LLM call failed: %s", exc)
        return {
            "guidance_items": [],
            "errors": state.get("errors", []) + ["Guidance extraction LLM call failed"],
        }

    cleaned = _strip_json_fences(raw)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Guidance extraction JSON parse error.")
        return {
            "guidance_items": [],
            "errors": state.get("errors", []) + ["Guidance extraction JSON parse error"],
        }

    if not isinstance(parsed, list):
        logger.error("Guidance extraction returned non-list JSON.")
        return {
            "guidance_items": [],
            "errors": state.get("errors", []) + ["Guidance extraction JSON parse error"],
        }

    required = {"metric", "guidance_value", "certainty_language", "speaker", "quote"}
    validated_items = []
    for item in parsed:
        if isinstance(item, dict) and required.issubset(item.keys()):
            validated_items.append(item)

    logger.info(
        "Guidance extracted: %d raw items, %d validated items.",
        len(parsed),
        len(validated_items),
    )
    return {"guidance_items": validated_items}
