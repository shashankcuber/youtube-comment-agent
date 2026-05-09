from typing import List, Optional, Dict, Any

from models import ParsedComment, SentimentGroup, RecommendationResult, LLMStatus
from llm_client import LocalLLMClient


class RecommendationAgent:
    """
    Agent 3:
    - First performs rule-based grouping and scoring.
    - Then optionally asks a local LLM to improve the final summary/recommendation.
    - If the LLM fails, it always falls back to the rule-based output.
    """

    def __init__(self, llm_client: Optional[LocalLLMClient] = None):
        self.llm_client = llm_client

        self.positive_words = [
            "helpful", "clear", "great", "excellent", "amazing",
            "useful", "best", "love", "easy to understand",
            "well explained", "good explanation", "thank you",
            "thanks", "perfect", "awesome", "informative"
        ]

        self.negative_words = [
            "bad", "boring", "confusing", "waste", "too long",
            "not helpful", "poor", "wrong", "terrible",
            "hard to understand", "disappointed", "unclear",
            "annoying", "slow"
        ]

        self.warning_words = [
            "outdated", "misleading", "clickbait", "incorrect",
            "fake", "not accurate", "old version", "doesn't work",
            "does not work", "error", "mistake", "wrong information"
        ]

    def classify_comment(self, comment: ParsedComment) -> str:
        text = comment.clean_text.lower()

        if any(word in text for word in self.warning_words):
            return "warning"

        if any(word in text for word in self.positive_words):
            return "positive"

        if any(word in text for word in self.negative_words):
            return "negative"

        if comment.possible_question:
            return "neutral"

        return "neutral"

    def extract_examples(self, comments: List[ParsedComment], limit: int = 3) -> List[str]:
        sorted_comments = sorted(comments, key=lambda c: c.like_count, reverse=True)
        return [comment.clean_text for comment in sorted_comments[:limit]]

    def calculate_rating(
        self,
        positive_count: int,
        negative_count: int,
        warning_count: int,
        total_count: int
    ) -> float:
        if total_count == 0:
            return 0.0

        score = 5.0

        positive_ratio = positive_count / total_count
        negative_ratio = negative_count / total_count
        warning_ratio = warning_count / total_count

        score += positive_ratio * 5.0
        score -= negative_ratio * 3.0
        score -= warning_ratio * 4.0

        return round(max(0.0, min(10.0, score)), 1)

    def generate_recommendation(
        self,
        rating: float,
        warning_count: int,
        total_count: int
    ) -> str:
        warning_ratio = warning_count / total_count if total_count else 0

        if total_count == 0:
            return "Not enough useful comments were available to make a recommendation."

        if warning_ratio > 0.25:
            return "Be careful. Many useful comments mention issues such as outdated, misleading, or incorrect information."

        if rating >= 8:
            return "Strongly recommended. Viewers are mostly positive about this video."

        if rating >= 6:
            return "Worth watching, but skim if you already know the basics."

        if rating >= 4:
            return "Mixed reaction. Watch only if the topic is important to you."

        return "Not recommended. Many viewers seem unsatisfied."

    def generate_summary(
        self,
        positive_count: int,
        negative_count: int,
        neutral_count: int,
        warning_count: int,
        total_count: int
    ) -> str:
        if total_count == 0:
            return "Not enough useful comments were available to summarize this video."

        positive_ratio = positive_count / total_count
        negative_ratio = negative_count / total_count
        warning_ratio = warning_count / total_count

        if warning_ratio > 0.25:
            return (
                "The comment section contains several warning signs. "
                "Many viewers mention possible outdated, misleading, or incorrect information."
            )

        if positive_ratio > 0.6:
            return (
                "Most useful comments are positive. Viewers generally seem to find the video helpful, "
                "clear, or worth watching."
            )

        if negative_ratio > 0.4:
            return (
                "Viewer reaction appears negative or mixed. Several users complain about quality, "
                "clarity, pacing, or usefulness."
            )

        return (
            "Viewer reaction is mixed. Some users found the video useful, while others had concerns "
            "or asked follow-up questions."
        )

    def get_overall_sentiment(
        self,
        positive_count: int,
        negative_count: int,
        neutral_count: int,
        warning_count: int
    ) -> str:
        counts = {
            "mostly_positive": positive_count,
            "mostly_negative": negative_count,
            "mostly_neutral": neutral_count,
            "warning_heavy": warning_count
        }

        return max(counts, key=counts.get)

    def analyze(self, comments: List[ParsedComment]) -> RecommendationResult:
        positive = []
        negative = []
        neutral = []
        warning = []

        for comment in comments:
            label = self.classify_comment(comment)

            if label == "positive":
                positive.append(comment)
            elif label == "negative":
                negative.append(comment)
            elif label == "warning":
                warning.append(comment)
            else:
                neutral.append(comment)

        total = len(comments)

        rating = self.calculate_rating(
            positive_count=len(positive),
            negative_count=len(negative),
            warning_count=len(warning),
            total_count=total
        )

        recommendation = self.generate_recommendation(
            rating=rating,
            warning_count=len(warning),
            total_count=total
        )

        summary = self.generate_summary(
            positive_count=len(positive),
            negative_count=len(negative),
            neutral_count=len(neutral),
            warning_count=len(warning),
            total_count=total
        )

        overall_sentiment = self.get_overall_sentiment(
            len(positive), len(negative), len(neutral), len(warning)
        )

        groups = [
            SentimentGroup(
                label="positive",
                count=len(positive),
                examples=self.extract_examples(positive)
            ),
            SentimentGroup(
                label="negative",
                count=len(negative),
                examples=self.extract_examples(negative)
            ),
            SentimentGroup(
                label="neutral",
                count=len(neutral),
                examples=self.extract_examples(neutral)
            ),
            SentimentGroup(
                label="warning",
                count=len(warning),
                examples=self.extract_examples(warning)
            )
        ]

        positives = [
            "Viewers mention that the video is helpful, clear, or useful."
        ] if positive else []

        negatives = [
            "Some viewers complain about pacing, usefulness, clarity, or quality."
        ] if negative else []

        warnings = [
            "Some viewers mention possible outdated, misleading, or incorrect information."
        ] if warning else []

        llm_status = LLMStatus(
            attempted=False,
            success=False,
            provider=self.llm_client.provider if self.llm_client else None,
            model=self.llm_client.model if self.llm_client else None,
            source="rule_based",
            error=None
        )

        llm_data = None

        if self.llm_client and self.llm_client.enabled and total > 0:
            llm_status.attempted = True

            rule_based_stats: Dict[str, Any] = {
                "positive_count": len(positive),
                "negative_count": len(negative),
                "neutral_count": len(neutral),
                "warning_count": len(warning),
                "total_comments": total,
                "overall_sentiment": overall_sentiment,
                "rule_based_rating": rating,
                "rule_based_summary": summary,
                "rule_based_recommendation": recommendation
            }

            comment_texts = [comment.clean_text for comment in comments]

            try:
                llm_data = self.llm_client.generate_watch_recommendation(
                    comments=comment_texts,
                    rule_based_stats=rule_based_stats
                )

                llm_status.success = True
                llm_status.source = "llm"

            except Exception as error:
                llm_status.success = False
                llm_status.source = "rule_based_fallback"
                llm_status.error = str(error)

        if llm_data:
            return RecommendationResult(
                overall_sentiment=overall_sentiment,
                watch_rating=llm_data.get("rating", rating),
                recommendation=llm_data.get("recommendation", recommendation),
                summary=llm_data.get("summary", summary),
                positives=positives,
                negatives=negatives,
                warnings=warnings,
                groups=groups,
                total_comments_analyzed=total,

                result_source="llm",
                llm_status=llm_status,

                llm_summary=llm_data.get("summary"),
                llm_recommendation=llm_data.get("recommendation"),
                llm_decision=llm_data.get("decision"),
                llm_confidence=llm_data.get("confidence"),
                llm_positive_themes=llm_data.get("positive_themes"),
                llm_negative_themes=llm_data.get("negative_themes"),
                llm_warning_themes=llm_data.get("warning_themes")
            )

        return RecommendationResult(
            overall_sentiment=overall_sentiment,
            watch_rating=rating,
            recommendation=recommendation,
            summary=summary,
            positives=positives,
            negatives=negatives,
            warnings=warnings,
            groups=groups,
            total_comments_analyzed=total,

            result_source=llm_status.source,
            llm_status=llm_status
        )