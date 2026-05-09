from typing import List
from models import ParsedComment, SentimentGroup, RecommendationResult


class RecommendationAgent:
    """
    Agent 3:
    Groups comments and creates final watch recommendation.
    """

    def __init__(self):
        self.positive_words = [
            "helpful", "clear", "great", "excellent", "amazing",
            "useful", "best", "love", "easy to understand",
            "well explained", "good explanation", "thank you"
        ]

        self.negative_words = [
            "bad", "boring", "confusing", "waste", "too long",
            "not helpful", "poor", "wrong", "terrible",
            "hard to understand", "disappointed"
        ]

        self.warning_words = [
            "outdated", "misleading", "clickbait", "incorrect",
            "fake", "not accurate", "old version", "doesn't work",
            "error", "mistake"
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

    def generate_recommendation(self, rating: float, warning_count: int, total_count: int) -> str:
        warning_ratio = warning_count / total_count if total_count else 0

        if warning_ratio > 0.25:
            return "Be careful. Many viewers mention issues like outdated, misleading, or incorrect information."

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
                "Many viewers mention problems such as outdated, misleading, or incorrect information."
            )

        if positive_ratio > 0.6:
            return (
                "Most useful comments are positive. Viewers generally seem to find the video helpful, "
                "clear, or worth watching."
            )

        if negative_ratio > 0.4:
            return (
                "Viewer reaction appears negative or mixed. Several users complain about the quality, "
                "clarity, pacing, or usefulness of the video."
            )

        return (
            "Viewer reaction is mixed. Some users found the video useful, while others had concerns "
            "or asked follow-up questions."
        )

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
            "Viewers mention that the video is helpful or clear."
        ] if positive else []

        negatives = [
            "Some viewers complain about pacing, usefulness, or clarity."
        ] if negative else []

        warnings = [
            "Some viewers mention possible outdated, misleading, or incorrect information."
        ] if warning else []

        overall_sentiment = self.get_overall_sentiment(
            len(positive), len(negative), len(neutral), len(warning)
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
            total_comments_analyzed=total
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