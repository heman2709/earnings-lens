from langgraph.graph import END, StateGraph

from agents.actuals_extractor import extract_actuals
from agents.credibility_scorer import score_credibility
from agents.guidance_extractor import extract_guidance
from agents.report_generator import generate_report
from agents.transcript_loader import load_transcripts
from pipeline.guardrails import input_guard, output_guard
from pipeline.state import EarningsState, create_initial_state


def _after_input_guard(state: EarningsState) -> str:
    """Route after input guard based on validation result.

    Args:
        state: Current state after input_guard.

    Returns:
        Next node name or END.

    Raises:
        None.
    """
    return "load_transcripts" if state.get("input_valid", False) else END


def _after_transcript_loader(state: EarningsState) -> str:
    """Route after transcript loading based on availability and validity.

    Args:
        state: Current state after load_transcripts.

    Returns:
        Next node name or END.

    Raises:
        None.
    """
    return "extract_guidance" if state.get("input_valid", False) else END


def build_graph():
    """Build and compile the EarningsLens LangGraph pipeline.

    Args:
        None.

    Returns:
        Compiled LangGraph app instance.

    Raises:
        None.
    """
    graph = StateGraph(EarningsState)

    graph.add_node("input_guard", input_guard)
    graph.add_node("load_transcripts", load_transcripts)
    graph.add_node("extract_guidance", extract_guidance)
    graph.add_node("extract_actuals", extract_actuals)
    graph.add_node("score_credibility", score_credibility)
    graph.add_node("generate_report", generate_report)
    graph.add_node("output_guard", output_guard)

    graph.set_entry_point("input_guard")
    graph.add_conditional_edges("input_guard", _after_input_guard)
    graph.add_conditional_edges("load_transcripts", _after_transcript_loader)
    graph.add_edge("extract_guidance", "extract_actuals")
    graph.add_edge("extract_actuals", "score_credibility")
    graph.add_edge("score_credibility", "generate_report")
    graph.add_edge("generate_report", "output_guard")
    graph.add_edge("output_guard", END)

    return graph.compile()


app = build_graph()


def run_pipeline(ticker: str, quarter: str) -> EarningsState:
    """Run the full EarningsLens graph for a ticker-quarter pair.

    Args:
        ticker: Company ticker symbol.
        quarter: Quarter in YYYY-QN format.

    Returns:
        Final pipeline state after all graph nodes execute.

    Raises:
        None.
    """
    initial_state = create_initial_state(ticker, quarter)
    result = app.invoke(initial_state)
    return result
