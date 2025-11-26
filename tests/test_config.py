"""Tests for configuration management."""

import os
import tempfile
from pathlib import Path
import pytest

from command_line_assistant.config import Config, get_config, ConfigurationError


def test_default_config():
    """Test default configuration values."""
    config = Config()
    assert config.ollama_endpoint == "http://localhost:11434/api/generate"
    assert config.ollama_model == "mistral-nemo"
    assert config.ollama_temperature == 0.1


def test_config_from_file():
    """Test loading configuration from a file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(
            """[ollama]
endpoint = "http://example.com:11434/api/generate"
model = "mistral"
temperature = 0.9
"""
        )
        config_path = Path(f.name)

    try:
        config = Config(config_path=config_path)
        assert config.ollama_endpoint == "http://example.com:11434/api/generate"
        assert config.ollama_model == "mistral"
        assert config.ollama_temperature == 0.9
    finally:
        config_path.unlink()


def test_config_environment_overrides():
    """Test environment variable overrides."""
    os.environ["OLLAMA_ENDPOINT"] = "http://test:11434/api/generate"
    os.environ["OLLAMA_MODEL"] = "test-model"
    os.environ["OLLAMA_TEMPERATURE"] = "0.5"

    try:
        config = Config()
        assert config.ollama_endpoint == "http://test:11434/api/generate"
        assert config.ollama_model == "test-model"
        assert config.ollama_temperature == 0.5
    finally:
        os.environ.pop("OLLAMA_ENDPOINT", None)
        os.environ.pop("OLLAMA_MODEL", None)
        os.environ.pop("OLLAMA_TEMPERATURE", None)


def test_config_invalid_temperature():
    """Test validation of temperature values."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(
            """[ollama]
temperature = 3.0
"""
        )
        config_path = Path(f.name)

    try:
        with pytest.raises(ConfigurationError, match="Temperature must be between"):
            Config(config_path=config_path)
    finally:
        config_path.unlink()


def test_config_invalid_file():
    """Test handling of invalid config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("invalid toml content {")
        config_path = Path(f.name)

    try:
        with pytest.raises(ConfigurationError):
            Config(config_path=config_path)
    finally:
        config_path.unlink()


def test_config_nonexistent_file():
    """Test handling of non-existent config file."""
    with pytest.raises(ConfigurationError, match="Config file not found"):
        Config(config_path=Path("/nonexistent/path/config.toml"))


def test_get_config():
    """Test get_config helper function."""
    config = get_config()
    assert isinstance(config, Config)
    assert config.ollama_endpoint is not None

