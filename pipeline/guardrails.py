import logging
import re

from pipeline.state import EarningsState


logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    "ignore previous",
    "ignore all",
    "disregard",
    "you are now",
    "act as",
    "jailbreak",
    "drop table",
    "select * from",
    "--",
    ";<",
    "system prompt",
]


def input_guard(state: EarningsState) -> dict:
    """
    LangGraph node — validates all inputs before pipeline starts.

    Checks:
    1. ticker: non-empty, 1-10 chars, letters/dots/hyphens only
       valid examples: "AAPL", "BRK.B", "BILI"
       regex: r'^[A-Za-z][A-Za-z0-9.\\-]{0,9}$'

    2. quarter: must match r'^\\d{4}-Q[1-4]$'
       valid: "2020-Q3", "2019-Q4"
       invalid: "Q3-2020", "2020Q3", "20-Q1"

    3. prompt injection: scan BOTH ticker and quarter against
       INJECTION_PATTERNS (case-insensitive)

    4. year sanity: year in quarter must be between 2000 and 2030

    Returns dict with ONLY changed fields:
    - If all valid: {"input_valid": True}
    - If any fail: {"input_valid": False, "errors": [list of messages]}

    IMPORTANT: On failure, do NOT raise exception.
    Return the dict — LangGraph will handle routing.
    """
    errors: list[str] = []

    ticker = str(state.get("ticker", "")).strip()
    quarter = str(state.get("quarter", "")).strip()

    ticker_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9.\-]{0,9}$")
    quarter_pattern = re.compile(r"^\d{4}-Q[1-4]$")

    if not ticker_pattern.match(ticker):
        errors.append(
            "Invalid ticker: must match ^[A-Za-z][A-Za-z0-9.\\-]{0,9}$ "
            "(examples: AAPL, BRK.B, BILI)."
        )

    if not quarter_pattern.match(quarter):
        errors.append(
            "Invalid quarter format: must match ^\\d{4}-Q[1-4]$ "
            "(examples: 2020-Q3, 2019-Q4)."
        )

    combined_values = f"{ticker} {quarter}".lower()
    for pattern in INJECTION_PATTERNS:
        if pattern.lower() in combined_values:
            errors.append(f"Potential prompt injection detected: '{pattern}'.")
            break

    if quarter_pattern.match(quarter):
        year = int(quarter[:4])
        if year < 2000 or year > 2030:
            errors.append("Invalid quarter year: must be between 2000 and 2030.")

    if errors:
        logger.warning("Input guard failed with %d error(s).", len(errors))
        return {"input_valid": False, "errors": errors}

    return {"input_valid": True}


def output_guard(state: EarningsState) -> dict:
    """
    LangGraph node — validates pipeline output before returning.

    Checks:
    1. report is non-empty string (len > 50)
    2. credibility_score is float between 0.0 and 100.0
    3. guidance_items — each item has required keys:
       [metric, guidance_value, certainty_language, speaker, quote]
    4. actual_items — each item has required keys:
       [metric, actual_value, source_quote]
    5. PII check: report must not contain sequences of
       12+ consecutive digits (account numbers, SSNs etc.)
       regex: r'\\b\\d{12,}\\b'
    6. route must be one of: "red_flag", "clean_bill"

    Returns:
    - If all pass: {"output_valid": True}
    - If any fail: {"output_valid": False, "errors": [appended messages]}

    On errors, APPEND to existing state["errors"], don't overwrite.
    """
    errors: list[str] = list(state.get("errors", []))
    new_errors: list[str] = []

    report = state.get("report", "")
    if not isinstance(report, str) or len(report.strip()) <= 50:
        new_errors.append("Report must be a non-empty string with length > 50.")

    score = state.get("credibility_score", None)
    if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 100.0):
        new_errors.append("Credibility score must be a float between 0.0 and 100.0.")

    guidance_items = state.get("guidance_items", [])
    guidance_required = {
        "metric",
        "guidance_value",
        "certainty_language",
        "speaker",
        "quote",
    }
    if not isinstance(guidance_items, list):
        new_errors.append("guidance_items must be a list.")
    else:
        for idx, item in enumerate(guidance_items):
            if not isinstance(item, dict):
                new_errors.append(f"guidance_items[{idx}] must be a dict.")
                continue
            missing = guidance_required.difference(item.keys())
            if missing:
                new_errors.append(
                    f"guidance_items[{idx}] missing required keys: {sorted(missing)}."
                )

    actual_items = state.get("actual_items", [])
    actual_required = {"metric", "actual_value", "source_quote"}
    if not isinstance(actual_items, list):
        new_errors.append("actual_items must be a list.")
    else:
        for idx, item in enumerate(actual_items):
            if not isinstance(item, dict):
                new_errors.append(f"actual_items[{idx}] must be a dict.")
                continue
            missing = actual_required.difference(item.keys())
            if missing:
                new_errors.append(
                    f"actual_items[{idx}] missing required keys: {sorted(missing)}."
                )

    if isinstance(report, str) and re.search(r"\b\d{12,}\b", report):
        new_errors.append("Report may contain sensitive numeric PII (12+ digits).")

    route = state.get("route", "")
    if route not in {"red_flag", "clean_bill"}:
        new_errors.append("Route must be one of: 'red_flag', 'clean_bill'.")

    if new_errors:
        errors.extend(new_errors)
        logger.warning("Output guard failed with %d new error(s).", len(new_errors))
        return {"output_valid": False, "errors": errors}

    return {"output_valid": True}


if __name__ == "__main__":
    from pipeline.state import create_initial_state

    # Test 1: valid input
    s = create_initial_state("AAPL", "2020-Q3")
    result = input_guard(s)
    assert result["input_valid"] is True, "Valid input failed"
    print("✅ Test 1 passed: valid input accepted")

    # Test 2: bad ticker
    s = create_initial_state("123INVALID!!!", "2020-Q3")
    result = input_guard(s)
    assert result["input_valid"] is False, "Bad ticker not caught"
    print("✅ Test 2 passed: bad ticker caught:", result["errors"])

    # Test 3: bad quarter format
    s = create_initial_state("AAPL", "Q3-2020")
    result = input_guard(s)
    assert result["input_valid"] is False, "Bad quarter not caught"
    print("✅ Test 3 passed: bad quarter caught:", result["errors"])

    # Test 4: prompt injection
    s = create_initial_state("IGNORE PREVIOUS", "2020-Q3")
    result = input_guard(s)
    assert result["input_valid"] is False, "Injection not caught"
    print("✅ Test 4 passed: injection caught:", result["errors"])

    # Test 5: year out of range
    s = create_initial_state("AAPL", "1995-Q3")
    result = input_guard(s)
    assert result["input_valid"] is False, "Year not validated"
    print("✅ Test 5 passed: year range caught:", result["errors"])

    print("\n✅ All guardrail tests passed.")
