"""Tests for Ollama client."""

import json
from unittest.mock import Mock, patch, MagicMock
import pytest
import requests

from command_line_assistant.client import OllamaClient
from command_line_assistant.config import Config
from command_line_assistant.exceptions import (
    OllamaConnectionError,
    OllamaAPIError,
)


def test_client_initialization():
    """Test client initialization with config."""
    config = Config()
    client = OllamaClient(config)
    assert client.endpoint == config.ollama_endpoint
    assert client.model == config.ollama_model
    assert client.temperature == config.ollama_temperature


def test_client_default_config():
    """Test client initialization without config."""
    client = OllamaClient()
    assert client.endpoint is not None
    assert client.model is not None


@patch("command_line_assistant.client.requests.post")
def test_generate_streaming(mock_post):
    """Test streaming response generation."""
    # Mock streaming response
    response_lines = [
        b'{"response": "Hello", "done": false}\n',
        b'{"response": " world", "done": false}\n',
        b'{"response": "!", "done": true}\n',
    ]

    mock_response = Mock()
    mock_response.iter_lines.return_value = response_lines
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    client = OllamaClient()
    chunks = list(client.generate("test prompt"))

    assert chunks == ["Hello", " world", "!"]
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[1]["json"]["model"] == client.model
    assert call_args[1]["json"]["prompt"] == "test prompt"
    assert call_args[1]["json"]["stream"] is True


@patch("command_line_assistant.client.requests.post")
def test_generate_non_streaming(mock_post):
    """Test non-streaming response generation."""
    mock_response = Mock()
    mock_response.json.return_value = {"response": "Complete response"}
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    client = OllamaClient()
    response = client.generate_complete("test prompt")

    assert response == "Complete response"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[1]["json"]["stream"] is False


@patch("command_line_assistant.client.requests.post")
def test_connection_error(mock_post):
    """Test handling of connection errors."""
    mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

    client = OllamaClient()
    with pytest.raises(OllamaConnectionError):
        list(client.generate("test prompt"))


@patch("command_line_assistant.client.requests.post")
def test_api_error(mock_post):
    """Test handling of API errors."""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "Server error"
    )
    mock_post.return_value = mock_response

    client = OllamaClient()
    with pytest.raises(OllamaAPIError):
        list(client.generate("test prompt"))


@patch("command_line_assistant.client.requests.post")
def test_timeout_error(mock_post):
    """Test handling of timeout errors."""
    mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

    client = OllamaClient()
    with pytest.raises(OllamaConnectionError):
        list(client.generate("test prompt"))


@patch("command_line_assistant.client.requests.post")
def test_test_connection_success(mock_post):
    """Test connection test with successful response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    client = OllamaClient()
    assert client.test_connection() is True


@patch("command_line_assistant.client.requests.post")
def test_test_connection_failure(mock_post):
    """Test connection test with failed response."""
    mock_post.side_effect = requests.exceptions.ConnectionError()

    client = OllamaClient()
    assert client.test_connection() is False

