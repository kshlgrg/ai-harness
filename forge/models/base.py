"""Model Provider Base Interface."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.2) -> str:
        """Generate text completion from model."""
        pass

    def generate_structured(self, prompt: str, schema: Type[T], system_prompt: str = "") -> T:
        """Generate and parse structured output matching a Pydantic schema."""
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        enhanced_prompt = (
            f"{prompt}\n\n"
            f"You MUST respond ONLY with valid JSON conforming strictly to the following JSON schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do not include any conversational preamble or commentary outside the JSON block."
        )
        response_text = self.generate(enhanced_prompt, system_prompt=system_prompt, temperature=0.1)
        return self._extract_and_parse_json(response_text, schema)

    @staticmethod
    def _extract_and_parse_json(text: str, schema: Type[T]) -> T:
        """Extract JSON from possible markdown wrapping and validate."""
        clean_text = text.strip()
        # Look for markdown json block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text)
        if match:
            clean_text = match.group(1).strip()
        
        # Fallback to finding outermost { ... } or [ ... ]
        first_brace = clean_text.find("{")
        last_brace = clean_text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            clean_text = clean_text[first_brace : last_brace + 1]

        data = json.loads(clean_text)
        return schema.model_validate(data)
