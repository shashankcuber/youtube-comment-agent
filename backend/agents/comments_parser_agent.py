import re
from typing import List
from models import RawComment, ParsedComment


class CommentParserAgent:
    """
    Agent 1:
    Converts raw YouTube comments into clean structured comments.
    """

    def clean_text(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"http\S+", "", text)
        return text

    def has_timestamp(self, text: str) -> bool:
        """
        Detects timestamps like:
        1:23
        12:45
        01:02:33
        """
        timestamp_pattern = r"\b(?:(?:\d{1,2}:)?\d{1,2}:\d{2})\b"
        return bool(re.search(timestamp_pattern, text))

    def is_question(self, text: str) -> bool:
        question_words = ["what", "why", "how", "when", "where", "can", "does", "is", "are"]
        lower_text = text.lower()

        return text.endswith("?") or any(
            lower_text.startswith(word + " ") for word in question_words
        )

    def parse(self, raw_comments: List[RawComment]) -> List[ParsedComment]:
        parsed_comments = []

        for comment in raw_comments:
            clean = self.clean_text(comment.text)

            if not clean:
                continue

            parsed_comments.append(
                ParsedComment(
                    comment_id=comment.comment_id,
                    text=comment.text,
                    clean_text=clean,
                    like_count=comment.like_count,
                    word_count=len(clean.split()),
                    has_timestamp=self.has_timestamp(clean),
                    possible_question=self.is_question(clean)
                )
            )

        return parsed_comments