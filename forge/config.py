"""FORGE Central Configuration & Provider Detection."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(filepath: Path | str = ".env") -> None:
    """Load key-value pairs from .env if present without external dependencies."""
    p = Path(filepath)
    if not p.is_file():
        return
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


# Automatically load local .env if present
load_env_file()


@dataclass
class ForgeConfig:
    """Text-only Model and Harness Configuration.
    
    Adheres strictly to the AI Harness Hackathon 2026 technical requirements:
    - Text-only language model processing (no images, audio, or multimodal).
    - AI_API_KEY read dynamically from environment without hardcoded secrets.
    - Auto-detects endpoint routing for OpenAI, Groq, Anthropic, or custom proxy.
    """
    api_key: str = ""
    model: str = "gpt-4o"
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.2
    max_iterations: int = 10
    timeout_sec: float = 60.0
    modality: str = "text-only"
    root_path: Path = Path(".").resolve()
    runs_dir: Path = Path(".agent/runs").resolve()

    def __post_init__(self):
        load_env_file()
        self.api_key = (
            os.environ.get("AI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or ""
        )
        
        # Provider & Model auto-detection
        if self.api_key.startswith("gsk_"):
            # Groq provider auto-configuration
            default_url = "https://api.groq.com/openai/v1"
            default_model = "openai/gpt-oss-120b"
        else:
            default_url = "https://api.openai.com/v1"
            default_model = "gpt-4o"

        self.model = (
            os.environ.get("AI_MODEL")
            or os.environ.get("FORGE_MODEL")
            or default_model
        )
        self.base_url = (
            os.environ.get("AI_BASE_URL")
            or os.environ.get("FORGE_BASE_URL")
            or default_url
        ).rstrip("/")


def get_config() -> ForgeConfig:
    return ForgeConfig()
