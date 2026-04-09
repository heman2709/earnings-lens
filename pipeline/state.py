from typing import List, Optional, TypedDict


class EarningsState(TypedDict):
    # -- Inputs --------------------------------
    ticker: str
    quarter: str  # "2020-Q3"

    # -- Loaded transcripts --------------------
    current_transcript: str
    prior_transcript: str
    prior_quarter: str  # "2020-Q2" (derived)

    # -- Agent 2 output ------------------------
    guidance_items: List[dict]
    # Each dict has keys:
    # metric, guidance_value, certainty_language, speaker, quote

    # -- Agent 3 output ------------------------
    actual_items: List[dict]
    # Each dict has keys:
    # metric, actual_value, source_quote

    # -- Agent 4 output ------------------------
    credibility_score: float  # 0.0 to 100.0
    credibility_breakdown: List[dict]
    # Each dict has keys:
    # metric, guided, actual, verdict, delta
    # verdict is one of: "DELIVERED" | "PARTIAL" | "MISSED"
    language_drift_flags: List[str]

    # -- Routing -------------------------------
    route: str  # "red_flag" | "clean_bill"

    # -- Final output --------------------------
    report: str

    # -- Guardrail fields ----------------------
    input_valid: bool
    output_valid: bool
    errors: List[str]


def create_initial_state(ticker: str, quarter: str) -> EarningsState:
    """Create a fresh state with safe defaults for all fields.

    Args:
        ticker: Company ticker symbol.
        quarter: Quarter in YYYY-QN format.

    Returns:
        EarningsState with all required fields initialized.

    Raises:
        None.
    """
    safe_ticker: Optional[str] = ticker
    safe_quarter: Optional[str] = quarter

    return EarningsState(
        ticker=safe_ticker or "",
        quarter=safe_quarter or "",
        current_transcript="",
        prior_transcript="",
        prior_quarter="",
        guidance_items=[],
        actual_items=[],
        credibility_score=0.0,
        credibility_breakdown=[],
        language_drift_flags=[],
        route="",
        report="",
        input_valid=True,
        output_valid=False,
        errors=[],
    )
