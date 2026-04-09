import json
import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from pipeline.state import EarningsState
from utils.edgar_tool import fetch_edgar_summary


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


def extract_actuals(state: EarningsState) -> dict:
    """LangGraph node for structured current-quarter actuals extraction.

    LangGraph node — Agent 3: extracts reported financial results.
    Reads CURRENT quarter transcript (not prior).
    Also attempts ONE SEC EDGAR API call for the ticker.
    Calls OpenAI to extract structured actuals.
    Loads prompt from prompts/actuals_extractor.md.

    Args:
        state: EarningsState with current_transcript populated.

    Returns:
        Dict with actual_items list, or errors on failure.

    Raises:
        None.
    """
    if state.get("input_valid") is False:
        return {"errors": state.get("errors", [])}

    prompt_path = os.path.join(os.getcwd(), "prompts", "actuals_extractor.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        template = f.read()

    prompt = template.replace("{transcript}", state.get("current_transcript", ""))

    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        response = llm.invoke(prompt)
        raw = str(response.content).strip()
    except Exception as exc:
        logger.exception("Actuals extraction LLM call failed: %s", exc)
        return {
            "actual_items": [],
            "errors": state.get("errors", []) + ["Actuals extraction LLM call failed"],
        }

    cleaned = _strip_json_fences(raw)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Actuals extraction JSON parse error.")
        return {
            "actual_items": [],
            "errors": state.get("errors", []) + ["Actuals extraction JSON parse error"],
        }

    if not isinstance(parsed, list):
        logger.error("Actuals extraction returned non-list JSON.")
        return {
            "actual_items": [],
            "errors": state.get("errors", []) + ["Actuals extraction JSON parse error"],
        }

    required = {"metric", "actual_value", "source_quote"}
    validated_items = []
    for item in parsed:
        if isinstance(item, dict) and required.issubset(item.keys()):
            validated_items.append(item)

    logger.info(
        "Actuals extracted: %d raw items, %d validated items.",
        len(parsed),
        len(validated_items),
    )

    try:
        edgar_data = fetch_edgar_summary(state.get("ticker", ""))
        if edgar_data:
            logger.info("EDGAR data fetched successfully for %s.", state.get("ticker", ""))
    except Exception as exc:
        logger.warning("Unexpected EDGAR handling error: %s", exc)

    return {"actual_items": validated_items}


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv()

    from agents.guidance_extractor import extract_guidance
    from agents.transcript_loader import load_transcripts
    from pipeline.guardrails import input_guard
    from pipeline.state import create_initial_state

    # Build state through layers 1-3 first
    state = create_initial_state("BILI", "2020-Q2")
    state.update(input_guard(state))
    state.update(load_transcripts(state))

    print("=== Test 1: Guidance extraction (prior quarter) ===")
    result = extract_guidance(state)
    state.update(result)
    print(f"Guidance items found: {len(state['guidance_items'])}")
    if state["guidance_items"]:
        print("First item:")
        print(json.dumps(state["guidance_items"][0], indent=2))

    print("\n=== Test 2: Actuals extraction (current quarter) ===")
    result = extract_actuals(state)
    state.update(result)
    print(f"Actual items found: {len(state['actual_items'])}")
    if state["actual_items"]:
        print("First item:")
        print(json.dumps(state["actual_items"][0], indent=2))

    print("\n=== Test 3: EDGAR tool ===")
    from utils.edgar_tool import fetch_edgar_summary

    edgar = fetch_edgar_summary("AAPL")
    if edgar:
        print(f"✅ EDGAR: {edgar}")
    else:
        print("⚠️ EDGAR not available for this ticker (expected for BILI)")

    print("\n=== Test 4: Short-circuit on invalid state ===")
    bad_state = create_initial_state("ZZZZZ", "2020-Q2")
    bad_state["input_valid"] = False
    bad_state["errors"] = ["No transcript found"]
    result = extract_guidance(bad_state)
    assert "guidance_items" not in result or result.get("errors")
    print("✅ Short-circuit working")

    print("\n✅ Layer 4 complete.")
