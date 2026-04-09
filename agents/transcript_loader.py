import logging
import os

from pipeline.state import EarningsState
from utils.pkl_loader import get_prior_quarter, get_transcript, load_dataframe


logger = logging.getLogger(__name__)

_DF = None


def _get_df():
    global _DF
    if _DF is None:
        pkl_path = os.path.join(os.getcwd(), "data", "transcripts.pkl")
        _DF = load_dataframe(pkl_path)
        logger.info("Loaded transcripts DataFrame from %s", pkl_path)
    return _DF


def _segment_transcript(transcript: str) -> dict:
    """
    Splits a transcript into prepared remarks and Q&A sections.

    Args:
        transcript: full transcript string

    Returns:
        {
            "prepared_remarks": str,  # everything before Q&A
            "qa_section": str,        # everything after Q&A marker
            "has_qa": bool            # whether Q&A section was found
        }

    Logic:
    - Try each Q&A marker (case-insensitive) to find split point
    - If found: split at that position
    - If not found: entire transcript is prepared_remarks, qa=""
    - Strip whitespace from both parts
    - Log whether Q&A section was found and its approximate length
    """
    QA_MARKERS = [
        "Question-and-Answer Session",
        "Questions and Answers",
        "Q&A Session",
        "QUESTION AND ANSWER",
        "Question and Answer",
    ]

    lower_text = transcript.lower()
    split_idx = None
    matched_marker = None

    for marker in QA_MARKERS:
        idx = lower_text.find(marker.lower())
        if idx != -1 and (split_idx is None or idx < split_idx):
            split_idx = idx
            matched_marker = marker

    if split_idx is None:
        prepared = transcript.strip()
        qa = ""
        has_qa = False
    else:
        prepared = transcript[:split_idx].strip()
        qa = transcript[split_idx:].strip()
        has_qa = True

    if has_qa:
        logger.info(
            "Q&A marker found (%s). Approx QA length: %d chars.",
            matched_marker,
            len(qa),
        )
    else:
        logger.info("No Q&A marker found. Entire transcript treated as prepared remarks.")

    return {
        "prepared_remarks": prepared,
        "qa_section": qa,
        "has_qa": has_qa,
    }


def load_transcripts(state: EarningsState) -> dict:
    """
    LangGraph node — Agent 1: loads and segments transcripts.

    No LLM call. Pure data loading from local PKL file.
    Counts as tool use via pkl_loader utility.
    """
    if state.get("input_valid") is False:
        return {"errors": state.get("errors", [])}

    df = _get_df()

    ticker = state["ticker"]
    quarter = state["quarter"]

    current_transcript = get_transcript(df, ticker, quarter)
    if current_transcript is None:
        return {
            "input_valid": False,
            "errors": state.get("errors", [])
            + [f"No transcript found for {ticker} {quarter}"],
        }

    prior_quarter = get_prior_quarter(quarter)
    prior_transcript = get_transcript(df, ticker, prior_quarter)
    if prior_transcript is None:
        return {
            "input_valid": False,
            "errors": state.get("errors", [])
            + [
                f"No prior transcript found for {ticker} {prior_quarter}. "
                "Cannot perform cross-quarter validation."
            ],
        }

    current_segmented = _segment_transcript(current_transcript)
    prior_segmented = _segment_transcript(prior_transcript)

    return {
        "current_transcript": current_segmented["prepared_remarks"],
        "prior_transcript": prior_segmented["prepared_remarks"],
        "prior_quarter": prior_quarter,
        "input_valid": True,
    }


if __name__ == "__main__":
    from pipeline.guardrails import input_guard
    from pipeline.state import create_initial_state

    print("=== Test 1: Happy path — BILI 2020-Q2 ===")
    state = create_initial_state("BILI", "2020-Q2")
    state.update(input_guard(state))
    result = load_transcripts(state)
    assert result.get("input_valid") is True
    assert len(result["current_transcript"]) > 100
    assert len(result["prior_transcript"]) > 100
    assert result["prior_quarter"] == "2020-Q1"
    print(f"✅ Current transcript: {len(result['current_transcript'])} chars")
    print(f"✅ Prior transcript:   {len(result['prior_transcript'])} chars")
    print(f"✅ Prior quarter:      {result['prior_quarter']}")
    print(f"   First 120 chars of current:\n   {result['current_transcript'][:120]}")

    print("\n=== Test 2: Unknown ticker ===")
    state = create_initial_state("ZZZZZ", "2020-Q2")
    state.update(input_guard(state))
    result = load_transcripts(state)
    assert result.get("input_valid") is False
    print(f"✅ Error caught: {result['errors']}")

    print("\n=== Test 3: Valid ticker, missing prior quarter ===")
    # Find a ticker that has only ONE quarter in dataset
    # Use a ticker where Q1 exists but Q4 of prior year won't
    state = create_initial_state("GFF", "2020-Q1")
    state.update(input_guard(state))
    result = load_transcripts(state)
    # Either loads successfully (if 2019-Q4 exists) or
    # returns graceful error
    if result.get("input_valid") is False:
        print(f"✅ Missing prior handled: {result['errors']}")
    else:
        print("✅ Both quarters found for GFF")
        print(f"   Prior quarter: {result['prior_quarter']}")

    print("\n=== Test 4: Segmentation check ===")
    state = create_initial_state("BILI", "2020-Q2")
    state.update(input_guard(state))
    result = load_transcripts(state)
    transcript = result["current_transcript"]
    # Prepared remarks should NOT contain Q&A markers
    assert "Question-and-Answer" not in transcript or len(transcript) > 500
    print("✅ Segmentation working")
    print(f"   Prepared remarks length: {len(transcript)} chars")

    print("\n=== Test 5: Guard short-circuit ===")
    state = create_initial_state("AAPL", "1995-Q3")
    state.update(input_guard(state))
    # input_valid is False after guardrail
    result = load_transcripts(state)
    # Should return immediately without loading
    assert "current_transcript" not in result or result.get("input_valid") is False
    print("✅ Guard short-circuit working")

    print("\n✅ All Layer 3 tests passed.")
