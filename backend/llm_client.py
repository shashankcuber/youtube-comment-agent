import json
import re
from typing import Dict, Any, List

import requests

from config import (
    LLM_PROVIDER,
    LLM_MODEL,
    OLLAMA_BASE_URL,
    LLM_TIMEOUT_SECONDS,
)


class LocalLLMClient:
    """
    Local open-source LLM client using Ollama.

    v1.2.0:
    - Sends raw YouTube comments to the LLM.
    - Lets the LLM decide sentiment, authenticity signals, public opinion,
      and watch recommendation.
    """

    def __init__(self):
        self.provider = LLM_PROVIDER
        self.model = LLM_MODEL
        self.base_url = OLLAMA_BASE_URL.rstrip("/")
        self.timeout = LLM_TIMEOUT_SECONDS

    @property
    def enabled(self) -> bool:
        return self.provider.lower() == "ollama" and bool(self.model)

    def health_check(self) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "enabled": False,
                "provider": self.provider,
                "model": self.model,
                "ok": False,
                "error": "LLM provider is disabled or unsupported."
            }

        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            response.raise_for_status()

            data = response.json()
            available_models = [
                model.get("name") for model in data.get("models", [])
            ]

            return {
                "enabled": True,
                "provider": self.provider,
                "model": self.model,
                "ok": self.model in available_models,
                "available_models": available_models,
                "error": None if self.model in available_models else f"Model {self.model} is not pulled in Ollama."
            }

        except Exception as error:
            return {
                "enabled": True,
                "provider": self.provider,
                "model": self.model,
                "ok": False,
                "error": str(error)
            }

    def analyze_raw_comments(
        self,
        raw_comments: List[Dict[str, Any]],
        max_comments_for_llm: int = 80
    ) -> Dict[str, Any]:
        """
        Sends raw comments to the LLM and asks it to decide:
        - public sentiment
        - authenticity signals
        - watch recommendation
        """

        if not self.enabled:
            raise RuntimeError("Local LLM is disabled.")

        comments_for_prompt = self._prepare_comments_for_prompt(
            raw_comments=raw_comments,
            max_comments=max_comments_for_llm
        )

        system_prompt = """
You are a YouTube public sentiment analysis agent.

You analyze raw YouTube comments to estimate:
1. Overall public sentiment toward the video.
2. Whether the audience finds the video useful, misleading, authentic, low-quality, outdated, or controversial.
3. Whether a new viewer should watch, skim, skip, or remain uncertain.

Important rules:
- You did not watch the video.
- You only know the comments provided.
- Do not invent facts about the video.
- Do not claim the video is objectively true or false.
- Authenticity means perceived authenticity from comments only.
- Return valid JSON only.
"""

        user_payload = {
            "task": "Analyze raw YouTube comments for sentiment, public opinion, authenticity signals, and watch recommendation.",
            "comments": comments_for_prompt,
            "required_json_schema": {
                "overall_public_sentiment": "mostly_positive | mostly_negative | mixed | mostly_neutral | warning_heavy | uncertain",
                "sentiment_distribution": {
                    "positive": "number 0 to 1",
                    "negative": "number 0 to 1",
                    "neutral": "number 0 to 1",
                    "warning": "number 0 to 1"
                },
                "authenticity_score": "number from 0 to 10",
                "authenticity_label": "high_trust | medium_trust | low_trust | uncertain",
                "authenticity_explanation": "string",
                "public_opinion_summary": "string",
                "watch_decision": "watch | skim | skip | uncertain",
                "watch_rating": "number from 0 to 10",
                "recommendation": "string",
                "positive_themes": ["string"],
                "negative_themes": ["string"],
                "neutral_themes": ["string"],
                "warning_themes": ["string"],
                "evidence_comments": ["short comment excerpts or paraphrases"],
                "confidence": "low | medium | high"
            },
            "output_rules": [
                "Return JSON only.",
                "Keep the summary concise.",
                "Do not include markdown.",
                "Do not include chain-of-thought.",
                "If comments are too noisy or insufficient, use uncertain.",
                "Ratings must be between 0 and 10.",
                "Sentiment distribution values must be between 0 and 1 and should approximately sum to 1."
            ]
        }

        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt.strip()
                    },
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False)
                    }
                ],
                "options": {
                    "temperature": 0.1
                }
            },
            timeout=self.timeout
        )

        response.raise_for_status()
        data = response.json()

        content = data.get("message", {}).get("content", "")

        if not content:
            raise RuntimeError("LLM returned empty content.")

        parsed = self._parse_json_from_text(content)
        return self._validate_raw_comment_analysis(parsed)

    def _prepare_comments_for_prompt(
        self,
        raw_comments: List[Dict[str, Any]],
        max_comments: int
    ) -> List[Dict[str, Any]]:
        """
        Keeps prompt small enough for local models.
        Sort by like_count first so the model sees influential comments.
        """

        sorted_comments = sorted(
            raw_comments,
            key=lambda c: c.get("like_count", 0),
            reverse=True
        )

        prepared = []

        for comment in sorted_comments[:max_comments]:
            text = str(comment.get("text", "")).strip()

            if not text:
                continue

            prepared.append(
                {
                    "text": text[:600],
                    "like_count": comment.get("like_count", 0),
                    "published_at": comment.get("published_at")
                }
            )

        return prepared

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """
        Local models sometimes return:
        <think>...</think>
        { json }

        This removes thinking tags and extracts JSON.
        """

        text = text.strip()

        text = re.sub(
            r"<think>.*?</think>",
            "",
            text,
            flags=re.DOTALL | re.IGNORECASE
        ).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)

        if not match:
            raise ValueError(f"Could not find JSON in LLM response: {text[:500]}")

        return json.loads(match.group(0))

    def _validate_raw_comment_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        allowed_sentiments = {
            "mostly_positive",
            "mostly_negative",
            "mixed",
            "mostly_neutral",
            "warning_heavy",
            "uncertain"
        }

        allowed_trust_labels = {
            "high_trust",
            "medium_trust",
            "low_trust",
            "uncertain"
        }

        allowed_decisions = {
            "watch",
            "skim",
            "skip",
            "uncertain"
        }

        allowed_confidence = {
            "low",
            "medium",
            "high"
        }

        overall = str(data.get("overall_public_sentiment", "uncertain")).lower()
        if overall not in allowed_sentiments:
            overall = "uncertain"

        authenticity_label = str(data.get("authenticity_label", "uncertain")).lower()
        if authenticity_label not in allowed_trust_labels:
            authenticity_label = "uncertain"

        watch_decision = str(data.get("watch_decision", "uncertain")).lower()
        if watch_decision not in allowed_decisions:
            watch_decision = "uncertain"

        confidence = str(data.get("confidence", "low")).lower()
        if confidence not in allowed_confidence:
            confidence = "low"

        authenticity_score = self._clamp_float(
            data.get("authenticity_score", 5.0),
            0.0,
            10.0
        )

        watch_rating = self._clamp_float(
            data.get("watch_rating", 5.0),
            0.0,
            10.0
        )

        distribution = data.get("sentiment_distribution", {})
        sentiment_distribution = {
            "positive": self._clamp_float(distribution.get("positive", 0.0), 0.0, 1.0),
            "negative": self._clamp_float(distribution.get("negative", 0.0), 0.0, 1.0),
            "neutral": self._clamp_float(distribution.get("neutral", 0.0), 0.0, 1.0),
            "warning": self._clamp_float(distribution.get("warning", 0.0), 0.0, 1.0),
        }

        return {
            "overall_public_sentiment": overall,
            "sentiment_distribution": sentiment_distribution,
            "authenticity_score": round(authenticity_score, 1),
            "authenticity_label": authenticity_label,
            "authenticity_explanation": str(data.get("authenticity_explanation", "")).strip(),
            "public_opinion_summary": str(data.get("public_opinion_summary", "")).strip(),
            "watch_decision": watch_decision,
            "watch_rating": round(watch_rating, 1),
            "recommendation": str(data.get("recommendation", "")).strip(),
            "positive_themes": self._ensure_list(data.get("positive_themes", [])),
            "negative_themes": self._ensure_list(data.get("negative_themes", [])),
            "neutral_themes": self._ensure_list(data.get("neutral_themes", [])),
            "warning_themes": self._ensure_list(data.get("warning_themes", [])),
            "evidence_comments": self._ensure_list(data.get("evidence_comments", []))[:5],
            "confidence": confidence
        }

    def _clamp_float(self, value: Any, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except Exception:
            number = minimum

        return max(minimum, min(maximum, number))

    def _ensure_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]

        if isinstance(value, str) and value.strip():
            return [value.strip()]

        return []