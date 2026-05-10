from langgraph.graph import StateGraph, START, END

from graph.state import CommentAnalysisState
from graph.nodes import (
    quality_node,
    should_continue_after_quality,
    sentiment_node,
    authenticity_node,
    viewer_intent_node,
    controversy_node,
    final_decision_node,
    fallback_node,
)


def build_comment_analysis_graph():
    graph = StateGraph(CommentAnalysisState)

    graph.add_node("quality_check", quality_node)
    graph.add_node("sentiment_agent", sentiment_node)
    graph.add_node("authenticity_agent", authenticity_node)
    graph.add_node("viewer_intent_agent", viewer_intent_node)
    graph.add_node("controversy_agent", controversy_node)
    graph.add_node("final_decision", final_decision_node)
    graph.add_node("fallback", fallback_node)

    graph.add_edge(START, "quality_check")

    graph.add_conditional_edges(
        "quality_check",
        should_continue_after_quality,
        {
            "continue": "sentiment_agent",
            "fallback": "fallback"
        }
    )

    graph.add_edge("sentiment_agent", "authenticity_agent")
    graph.add_edge("authenticity_agent", "viewer_intent_agent")
    graph.add_edge("viewer_intent_agent", "controversy_agent")
    graph.add_edge("controversy_agent", "final_decision")

    graph.add_edge("final_decision", END)
    graph.add_edge("fallback", END)

    return graph.compile()