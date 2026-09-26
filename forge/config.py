"""FORGE Central Configuration & Model Specification."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ForgeConfig:
    """Text-only Model and Harness Configuration.
    
    Adheres strictly to the AI Harness Hackathon 2026 technical requirements:
    - Text-only language model processing (no images, audio, or multimodal).
    - AI_API_KEY read dynamically from environment without hardcoded secrets.
    - Allows the Organising Committee to prescribe any model via AI_MODEL or FORGE_MODEL.
    """
    # Credential (must be read from environment at runtime)
    api_key: str = os.environ.get("AI_API_KEY", "")
    
    # Model specification (text-only model family)
    model: str = (
        os.environ.get("AI_MODEL")
        or os.environ.get("FORGE_MODEL")
        or "gpt-4o"
    )
    
    # Base URL for API endpoint (standard OpenAI-compatible, LiteLLM proxy, etc.)
    base_url: str = (
        os.environ.get("AI_BASE_URL")
        or os.environ.get("FORGE_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    
    # Execution parameters
    temperature: float = float(os.environ.get("FORGE_TEMPERATURE", "0.2"))
    max_iterations: int = int(os.environ.get("FORGE_MAX_ITERATIONS", "10"))
    timeout_sec: float = float(os.environ.get("FORGE_TIMEOUT", "60.0"))
    
    # Modality constraint: STRICTLY TEXT-ONLY
    modality: str = "text-only"
    
    # Working directories
    root_path: Path = Path(".").resolve()
    runs_dir: Path = Path(".agent/runs").resolve()


def get_config() -> ForgeConfig:
    return ForgeConfig()
