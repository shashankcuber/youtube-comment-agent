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

    v1.1.0 responsibility:
    - Receive filtered comments + rule-based stats
    - Ask a local model such as qwen3:1.7b for a better final summary
    - Return structured JSON
    - Never crash the whole app if LLM fails
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
        """
        Checks if Ollama is reachable.
        """
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

    def generate_watch_recommendation(
        self,
        comments: List[str],
        rule_based_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calls Ollama /api/chat and asks the local model for JSON output.
        """

        if not self.enabled:
            raise RuntimeError("Local LLM is disabled.")

        comments_for_prompt = comments[:40]

        system_prompt = """
You are a YouTube comment analysis assistant.

Your job:
- Analyze only the provided comments and rule-based stats.
- Do not invent details about the video.
- Do not claim you watched the video.
- Produce a concise recommendation for whether the user should watch, skim, skip, or stay uncertain.
- Return valid JSON only.
"""

        user_payload = {
            "task": "Generate a watch recommendation from YouTube comments.",
            "rules": [
                "Use only the comments and stats provided.",
                "Return JSON only.",
                "The rating must be between 0 and 10.",
                "The decision must be one of: watch, skim, skip, uncertain.",
                "The confidence must be one of: low, medium, high.",
                "Keep summary and recommendation concise."
            ],
            "rule_based_stats": rule_based_stats,
            "sample_comments": comments_for_prompt,
            "required_json_schema": {
                "summary": "string",
                "recommendation": "string",
                "decision": "watch | skim | skip | uncertain",
                "rating": "number from 0 to 10",
                "positive_themes": ["string"],
                "negative_themes": ["string"],
                "warning_themes": ["string"],
                "confidence": "low | medium | high"
            }
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
                    "temperature": 0.2
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

        return self._validate_llm_output(parsed)

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """
        Some small local models may wrap JSON with extra text.
        This extracts the first JSON object safely.
        """
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)

        if not match:
            raise ValueError(f"Could not find JSON in LLM response: {text[:300]}")

        return json.loads(match.group(0))

    def _validate_llm_output(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalizes the LLM response so the rest of the app can trust it.
        """

        decision = str(data.get("decision", "uncertain")).lower()
        if decision not in {"watch", "skim", "skip", "uncertain"}:
            decision = "uncertain"

        confidence = str(data.get("confidence", "low")).lower()
        if confidence not in {"low", "medium", "high"}:
            confidence = "low"

        try:
            rating = float(data.get("rating", 5.0))
        except Exception:
            rating = 5.0

        rating = max(0.0, min(10.0, rating))

        return {
            "summary": str(data.get("summary", "")).strip(),
            "recommendation": str(data.get("recommendation", "")).strip(),
            "decision": decision,
            "rating": round(rating, 1),
            "positive_themes": self._ensure_list(data.get("positive_themes", [])),
            "negative_themes": self._ensure_list(data.get("negative_themes", [])),
            "warning_themes": self._ensure_list(data.get("warning_themes", [])),
            "confidence": confidence
        }

    def _ensure_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]

        if isinstance(value, str) and value.strip():
            return [value.strip()]

        return []