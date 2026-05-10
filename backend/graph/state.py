from typing import TypedDict, List, Dict, Any, Optional


class CommentAnalysisState(TypedDict, total=False):
    video_id: str

    raw_comments: List[Dict[str, Any]]
    comments_for_llm: List[Dict[str, Any]]

    quality_result: Dict[str, Any]
    sentiment_result: Dict[str, Any]
    authenticity_result: Dict[str, Any]
    viewer_intent_result: Dict[str, Any]
    controversy_result: Dict[str, Any]

    final_result: Dict[str, Any]

    errors: List[str]
    used_fallback: bool