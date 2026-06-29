import os
import pytest
from jarvis.config import load_config, Config


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        load_config()


def test_load_config_returns_config(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    config = load_config()
    assert isinstance(config, Config)
    assert config.api_key == "sk-test-key"
    assert config.model == "claude-sonnet-4-6"


def test_load_config_custom_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    config = load_config(model="claude-haiku-4-5-20251001")
    assert config.model == "claude-haiku-4-5-20251001"
