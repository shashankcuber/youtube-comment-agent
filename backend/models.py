from pydantic import BaseModel
from typing import List, Dict, Optional


class RawComment(BaseModel):
    comment_id: str
    author: Optional[str] = None
    text: str
    like_count: int = 0
    published_at: Optional[str] = None


class ParsedComment(BaseModel):
    comment_id: str
    text: str
    clean_text: str
    like_count: int
    word_count: int
    has_timestamp: bool
    possible_question: bool


class FilteredComments(BaseModel):
    useful_comments: List[ParsedComment]
    removed_comments: List[ParsedComment]
    removal_reasons: Dict[str, str]


class SentimentGroup(BaseModel):
    label: str
    count: int
    examples: List[str]


class LLMStatus(BaseModel):
    attempted: bool = False
    success: bool = False
    provider: Optional[str] = None
    model: Optional[str] = None
    source: str = "rule_based"
    error: Optional[str] = None


class RecommendationResult(BaseModel):
    overall_sentiment: str
    watch_rating: float
    recommendation: str
    summary: str
    positives: List[str]
    negatives: List[str]
    warnings: List[str]
    groups: List[SentimentGroup]
    total_comments_analyzed: int

    # Important for v1.1.0 display/debugging
    result_source: str = "rule_based"
    llm_status: LLMStatus = LLMStatus()

    # Optional LLM-enhanced fields
    llm_summary: Optional[str] = None
    llm_recommendation: Optional[str] = None
    llm_decision: Optional[str] = None
    llm_confidence: Optional[str] = None
    llm_positive_themes: Optional[List[str]] = None
    llm_negative_themes: Optional[List[str]] = None
    llm_warning_themes: Optional[List[str]] = None