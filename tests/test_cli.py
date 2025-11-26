"""Tests for CLI interface."""

import sys
from unittest.mock import patch, MagicMock
import pytest
from click.testing import CliRunner

from command_line_assistant.cli import main
from command_line_assistant.exceptions import (
    OllamaConnectionError,
    OllamaAPIError,
    ConfigurationError,
)


def test_cli_version():
    """Test CLI version option."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.2.4" in result.output


def test_cli_help():
    """Test CLI help option."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Command Line Assistant" in result.output


@patch("command_line_assistant.cli.OllamaClient")
@patch("command_line_assistant.cli.get_config")
def test_cli_single_query(mock_get_config, mock_client_class):
    """Test single query mode."""
    mock_config = MagicMock()
    mock_get_config.return_value = mock_config

    mock_client = MagicMock()
    mock_client.generate.return_value = ["Response", " text"]
    mock_client_class.return_value = mock_client

    runner = CliRunner()
    result = runner.invoke(main, ["test question"])

    assert result.exit_code == 0
    assert "Response" in result.output
    assert "text" in result.output
    mock_client.generate.assert_called_once_with("test question")


@patch("command_line_assistant.cli.OllamaClient")
@patch("command_line_assistant.cli.get_config")
def test_cli_connection_error(mock_get_config, mock_client_class):
    """Test handling of connection errors."""
    mock_config = MagicMock()
    mock_get_config.return_value = mock_config

    mock_client = MagicMock()
    mock_client.generate.side_effect = OllamaConnectionError("Connection failed")
    mock_client_class.return_value = mock_client

    runner = CliRunner()
    result = runner.invoke(main, ["test question"])

    assert result.exit_code == 1
    assert "Error" in result.output
    assert "Connection failed" in result.output


@patch("command_line_assistant.cli.get_config")
def test_cli_config_error(mock_get_config):
    """Test handling of configuration errors."""
    mock_get_config.side_effect = ConfigurationError("Config error")

    runner = CliRunner()
    result = runner.invoke(main, ["test question"])

    assert result.exit_code == 1
    assert "Error" in result.output
    assert "Config error" in result.output


@patch("command_line_assistant.cli.OllamaClient")
@patch("command_line_assistant.cli.get_config")
def test_cli_invalid_temperature(mock_get_config, mock_client_class):
    """Test handling of invalid temperature."""
    mock_config = MagicMock()
    mock_get_config.return_value = mock_config

    runner = CliRunner()
    result = runner.invoke(main, ["--temperature", "3.0", "test question"])

    assert result.exit_code == 1
    assert "Temperature must be between" in result.output

