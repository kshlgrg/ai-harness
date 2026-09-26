"""Live LLM Provider using AI_API_KEY with standard HTTP endpoints."""
from __future__ import annotations

import os
import httpx
from forge.config import get_config
from forge.models.base import ModelProvider


class LiveLLMProvider(ModelProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ):
        config = get_config()
        self.api_key = (
            api_key
            or os.environ.get("AI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or config.api_key
        )
        if not self.api_key:
            raise ValueError(
                "No API key provided. Please export AI_API_KEY before running."
            )

        self.model = (
            model
            or os.environ.get("AI_MODEL")
            or os.environ.get("FORGE_MODEL")
            or config.model
        )
        self.base_url = (
            base_url
            or os.environ.get("AI_BASE_URL")
            or os.environ.get("FORGE_BASE_URL")
            or config.base_url
        ).rstrip("/")
        self.timeout = timeout or config.timeout_sec

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.2) -> str:
        # Strictly text-only message format
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": str(system_prompt)})
        messages.append({"role": "user", "content": str(prompt)})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        url = f"{self.base_url}/chat/completions"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"LLM API request to {self.model} failed [{resp.status_code}]: {resp.text}"
                )
            data = resp.json()
            return data["choices"][0]["message"]["content"]
