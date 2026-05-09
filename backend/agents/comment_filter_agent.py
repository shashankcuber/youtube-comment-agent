import re
from typing import List, Dict, Set
from models import ParsedComment, FilteredComments


class CommentFilterAgent:
    """
    Agent 2:
    Filters useless, spammy, duplicate, or low-value comments.
    """

    def __init__(self):
        self.spam_keywords = [
            "subscribe to my channel",
            "check out my channel",
            "follow me",
            "free giveaway",
            "click my profile",
            "earn money fast",
            "telegram me",
            "whatsapp me"
        ]

        self.low_value_phrases = [
            "first",
            "nice",
            "cool",
            "wow",
            "lol",
            "great",
            "thanks",
            "good video",
            "awesome",
            "amazing"
        ]

    def is_emoji_only(self, text: str) -> bool:
        cleaned = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
        return len(cleaned) == 0

    def is_spam(self, text: str) -> bool:
        lower_text = text.lower()
        return any(keyword in lower_text for keyword in self.spam_keywords)

    def is_low_value(self, comment: ParsedComment) -> bool:
        lower_text = comment.clean_text.lower().strip()

        if comment.word_count <= 2:
            return True

        if lower_text in self.low_value_phrases:
            return True

        if self.is_emoji_only(comment.clean_text):
            return True

        return False

    def normalize_for_duplicate_check(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def filter(self, comments: List[ParsedComment]) -> FilteredComments:
        useful_comments: List[ParsedComment] = []
        removed_comments: List[ParsedComment] = []
        removal_reasons: Dict[str, str] = {}
        seen_texts: Set[str] = set()

        for comment in comments:
            normalized = self.normalize_for_duplicate_check(comment.clean_text)

            if self.is_spam(comment.clean_text):
                removed_comments.append(comment)
                removal_reasons[comment.comment_id] = "spam"
                continue

            if self.is_low_value(comment):
                removed_comments.append(comment)
                removal_reasons[comment.comment_id] = "low_value"
                continue

            if normalized in seen_texts:
                removed_comments.append(comment)
                removal_reasons[comment.comment_id] = "duplicate"
                continue

            seen_texts.add(normalized)
            useful_comments.append(comment)

        return FilteredComments(
            useful_comments=useful_comments,
            removed_comments=removed_comments,
            removal_reasons=removal_reasons
        )