import os
from dataclasses import dataclass


@dataclass
class Config:
    api_key: str
    model: str


def load_config(model: str = "claude-sonnet-4-6") -> Config:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Export it before running Jarvis: export ANTHROPIC_API_KEY=your_key"
        )
    return Config(api_key=api_key, model=model)
