from typing import List

from models import RawComment, PublicSentimentResult, LLMStatus
from llm_client import LocalLLMClient


class RawCommentLLMAgent:
    """
    v1.2.0 Agent:
    Lets the LLM directly analyze raw YouTube comments.

    It decides:
    - overall public sentiment
    - authenticity signals
    - public opinion
    - watch rating
    - watch / skim / skip recommendation
    """

    def __init__(self, llm_client: LocalLLMClient):
        self.llm_client = llm_client

    def analyze(
        self,
        raw_comments: List[RawComment],
        max_comments_for_llm: int = 80
    ) -> PublicSentimentResult:
        llm_status = LLMStatus(
            attempted=True,
            success=False,
            provider=self.llm_client.provider,
            model=self.llm_client.model,
            source="llm",
            error=None
        )

        raw_comment_dicts = [
            {
                "comment_id": comment.comment_id,
                "author": comment.author,
                "text": comment.text,
                "like_count": comment.like_count,
                "published_at": comment.published_at
            }
            for comment in raw_comments
        ]

        llm_data = self.llm_client.analyze_raw_comments(
            raw_comments=raw_comment_dicts,
            max_comments_for_llm=max_comments_for_llm
        )

        llm_status.success = True
        llm_status.source = "llm"

        return PublicSentimentResult(
            result_source="llm",
            llm_status=llm_status,

            total_raw_comments=len(raw_comments),
            comments_sent_to_llm=min(len(raw_comments), max_comments_for_llm),

            overall_public_sentiment=llm_data["overall_public_sentiment"],
            sentiment_distribution=llm_data["sentiment_distribution"],

            authenticity_score=llm_data["authenticity_score"],
            authenticity_label=llm_data["authenticity_label"],
            authenticity_explanation=llm_data["authenticity_explanation"],

            public_opinion_summary=llm_data["public_opinion_summary"],
            watch_decision=llm_data["watch_decision"],
            watch_rating=llm_data["watch_rating"],
            recommendation=llm_data["recommendation"],

            positive_themes=llm_data["positive_themes"],
            negative_themes=llm_data["negative_themes"],
            neutral_themes=llm_data["neutral_themes"],
            warning_themes=llm_data["warning_themes"],

            evidence_comments=llm_data["evidence_comments"],

            fallback_used=False,
            fallback_reason=None
        )