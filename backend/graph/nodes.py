from typing import Dict, Any


def quality_node(state: Dict[str, Any]) -> Dict[str, Any]:
    comments = state.get("comments_for_llm", [])

    if len(comments) < 10:
        return {
            "quality_result": {
                "comment_quality": "low",
                "analysis_confidence": "low",
                "reason": "Not enough comments for reliable analysis."
            }
        }

    short_comments = [
        c for c in comments
        if len(c.get("text", "").split()) <= 3
    ]

    short_ratio = len(short_comments) / max(len(comments), 1)

    if short_ratio > 0.6:
        quality = "low"
        confidence = "low"
    elif short_ratio > 0.35:
        quality = "medium"
        confidence = "medium"
    else:
        quality = "high"
        confidence = "high"

    return {
        "quality_result": {
            "comment_quality": quality,
            "short_comment_ratio": round(short_ratio, 2),
            "analysis_confidence": confidence
        }
    }


def should_continue_after_quality(state: Dict[str, Any]) -> str:
    quality = state.get("quality_result", {}).get("comment_quality")

    if quality == "low":
        return "fallback"

    return "continue"


def sentiment_node(state: Dict[str, Any]) -> Dict[str, Any]:
    # Later this can call the LLM with a sentiment-only prompt.
    # For now, keep it as a placeholder.

    return {
        "sentiment_result": {
            "overall": "uncertain",
            "positive": 0.0,
            "negative": 0.0,
            "neutral": 1.0,
            "warning": 0.0
        }
    }


def authenticity_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "authenticity_result": {
            "authenticity_score": 5.0,
            "authenticity_label": "uncertain",
            "reason": "Authenticity has not been deeply analyzed yet."
        }
    }


def viewer_intent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "viewer_intent_result": {
            "best_for": [],
            "not_best_for": [],
            "viewer_advice": "Not enough information yet."
        }
    }


def controversy_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "controversy_result": {
            "controversy_level": "uncertain",
            "conflicting_opinions": []
        }
    }


def final_decision_node(state: Dict[str, Any]) -> Dict[str, Any]:
    quality = state.get("quality_result", {})
    sentiment = state.get("sentiment_result", {})
    authenticity = state.get("authenticity_result", {})
    intent = state.get("viewer_intent_result", {})
    controversy = state.get("controversy_result", {})

    return {
        "final_result": {
            "decision": "uncertain",
            "rating": 5.0,
            "summary": "The graph ran successfully, but advanced LLM analysis is not fully connected yet.",
            "quality": quality,
            "sentiment": sentiment,
            "authenticity": authenticity,
            "viewer_intent": intent,
            "controversy": controversy
        }
    }


def fallback_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "used_fallback": True,
        "final_result": {
            "decision": "uncertain",
            "rating": 5.0,
            "summary": "Comment quality was too low for reliable analysis.",
            "quality": state.get("quality_result", {})
        }
    }