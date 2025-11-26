"""Ollama API client for command-line-assistant."""

import json
import logging
from typing import Optional, Iterator, Dict, Any

import requests

from command_line_assistant.config import Config
from command_line_assistant.exceptions import (
    OllamaConnectionError,
    OllamaAPIError,
)
from command_line_assistant.logger import get_logger, is_debug_mode


class OllamaClient:
    """Client for interacting with Ollama API."""

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize Ollama client.

        Args:
            config: Configuration instance. If not provided, loads default config.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        if config is None:
            from command_line_assistant.config import get_config

            config = get_config()

        self.config = config
        self.endpoint = config.ollama_endpoint
        self.model = config.ollama_model
        self.temperature = config.ollama_temperature
        self.logger = get_logger(f"{__name__}.OllamaClient")

    def _make_request(
        self, prompt: str, stream: bool = True, timeout: int = 30
    ) -> requests.Response:
        """
        Make a request to Ollama API.

        Args:
            prompt: The prompt to send to the model.
            stream: Whether to stream the response.
            timeout: Request timeout in seconds.

        Returns:
            Response object.

        Raises:
            OllamaConnectionError: If connection fails.
            OllamaAPIError: If API returns an error.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
            },
        }

        try:
            self.logger.debug(f"Making request to {self.endpoint} with model {self.model}")
            if is_debug_mode():
                self.logger.debug("=" * 80)
                self.logger.debug("OLLAMA REQUEST (generate API)")
                self.logger.debug("=" * 80)
                self.logger.debug(f"Endpoint: {self.endpoint}")
                self.logger.debug(f"Model: {self.model}")
                self.logger.debug(f"Temperature: {self.temperature}")
                self.logger.debug(f"Stream: {stream}")
                self.logger.debug(f"Timeout: {timeout}")
                self.logger.debug("-" * 80)
                self.logger.debug("PROMPT:")
                self.logger.debug(prompt)
                self.logger.debug("=" * 80)
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=timeout,
                stream=stream,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error to {self.endpoint}: {e}")
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {self.endpoint}: {e}"
            ) from e
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Request timeout after {timeout} seconds: {e}")
            raise OllamaConnectionError(
                f"Request to Ollama timed out after {timeout} seconds: {e}"
            ) from e
        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, 'status_code', 'unknown')
            self.logger.error(f"HTTP error {status_code}: {e}")
            raise OllamaAPIError(
                f"Ollama API returned error {status_code}: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise OllamaConnectionError(f"Request to Ollama failed: {e}") from e

    def generate(self, prompt: str, stream: bool = True) -> Iterator[str]:
        """
        Generate a response from Ollama.

        Args:
            prompt: The prompt to send to the model.
            stream: Whether to stream the response.

        Yields:
            Response chunks as strings.

        Raises:
            OllamaConnectionError: If connection fails.
            OllamaAPIError: If API returns an error.
        """
        if is_debug_mode():
            self.logger.debug("=" * 80)
            self.logger.debug("GENERATE (simple prompt)")
            self.logger.debug("=" * 80)
            self.logger.debug("PROMPT:")
            self.logger.debug(prompt)
            self.logger.debug("=" * 80)
        response = self._make_request(prompt, stream=stream)

        full_response = ""
        if stream:
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            chunk = data["response"]
                            full_response += chunk
                            yield chunk
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Failed to parse response line: {e}")
                        continue
            if is_debug_mode():
                self.logger.debug("=" * 80)
                self.logger.debug("OLLAMA RESPONSE (generate API - streaming)")
                self.logger.debug("=" * 80)
                self.logger.debug("FULL RESPONSE:")
                self.logger.debug(full_response)
                self.logger.debug("=" * 80)
        else:
            try:
                data = response.json()
                if "response" in data:
                    full_response = data["response"]
                    if is_debug_mode():
                        self.logger.debug("=" * 80)
                        self.logger.debug("OLLAMA RESPONSE (generate API - non-streaming)")
                        self.logger.debug("=" * 80)
                        self.logger.debug("FULL RESPONSE:")
                        self.logger.debug(full_response)
                        self.logger.debug("=" * 80)
                    yield full_response
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse Ollama response: {e}")
                raise OllamaAPIError(f"Failed to parse Ollama response: {e}") from e

    def generate_complete(self, prompt: str) -> str:
        """
        Generate a complete response from Ollama (non-streaming).

        Args:
            prompt: The prompt to send to the model.

        Returns:
            Complete response as a string.

        Raises:
            OllamaConnectionError: If connection fails.
            OllamaAPIError: If API returns an error.
        """
        response = self._make_request(prompt, stream=False)
        try:
            data = response.json()
            full_response = data.get("response", "")
            if is_debug_mode():
                self.logger.debug("=" * 80)
                self.logger.debug("OLLAMA RESPONSE (generate_complete)")
                self.logger.debug("=" * 80)
                self.logger.debug("FULL RESPONSE:")
                self.logger.debug(full_response)
                self.logger.debug("=" * 80)
            return full_response
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Ollama response: {e}")
            raise OllamaAPIError(f"Failed to parse Ollama response: {e}") from e

    def generate_with_system_prompt(
        self, user_prompt: str, system_prompt: str, stream: bool = True
    ) -> Iterator[str]:
        """
        Generate a response with a system prompt.

        Args:
            user_prompt: The user's prompt.
            system_prompt: The system prompt/instructions.
            stream: Whether to stream the response.

        Yields:
            Response chunks as strings.

        Raises:
            OllamaConnectionError: If connection fails.
            OllamaAPIError: If API returns an error.
        """
        # Combine system and user prompts in a clear format
        full_prompt = f"{system_prompt}\n\nUser request: {user_prompt}\n\nResponse:"
        # Note: generate() already logs responses in debug mode, so we don't need to log again here
        yield from self.generate(full_prompt, stream=stream)

    def _get_chat_endpoint(self) -> str:
        """
        Get the chat API endpoint from the generate endpoint.

        Returns:
            Chat endpoint URL.
        """
        # Convert /api/generate to /api/chat
        if "/api/generate" in self.endpoint:
            return self.endpoint.replace("/api/generate", "/api/chat")
        # If already chat endpoint, return as-is
        if "/api/chat" in self.endpoint:
            return self.endpoint
        # Fallback: append /chat if endpoint doesn't match expected pattern
        return self.endpoint.rstrip("/") + "/api/chat"

    def _make_chat_request(
        self,
        messages: list[Dict[str, str]],
        stream: bool = True,
        timeout: int = 30,
        format_schema: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """
        Make a request to Ollama Chat API.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            stream: Whether to stream the response.
            timeout: Request timeout in seconds.
            format_schema: Optional JSON schema for structured outputs.

        Returns:
            Response object.

        Raises:
            OllamaConnectionError: If connection fails.
            OllamaAPIError: If API returns an error.
        """
        chat_endpoint = self._get_chat_endpoint()
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
            },
        }

        # Add structured output format if provided
        if format_schema:
            payload["format"] = format_schema

        try:
            self.logger.debug(
                f"Making chat request to {chat_endpoint} with model {self.model}"
            )
            if format_schema:
                self.logger.debug("Using structured output format")
            if is_debug_mode():
                self.logger.debug("=" * 80)
                self.logger.debug("OLLAMA REQUEST (chat API)")
                self.logger.debug("=" * 80)
                self.logger.debug(f"Endpoint: {chat_endpoint}")
                self.logger.debug(f"Model: {self.model}")
                self.logger.debug(f"Temperature: {self.temperature}")
                self.logger.debug(f"Stream: {stream}")
                self.logger.debug(f"Timeout: {timeout}")
                if format_schema:
                    self.logger.debug("Structured output format: ENABLED")
                self.logger.debug("-" * 80)
                self.logger.debug("MESSAGES:")
                for i, msg in enumerate(messages):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    self.logger.debug(f"[{i+1}] Role: {role}")
                    self.logger.debug(f"Content ({len(content)} chars):")
                    self.logger.debug(content)
                    self.logger.debug("-" * 40)
                self.logger.debug("=" * 80)
            response = requests.post(
                chat_endpoint,
                json=payload,
                timeout=timeout,
                stream=stream,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error to {chat_endpoint}: {e}")
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {chat_endpoint}: {e}"
            ) from e
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Request timeout after {timeout} seconds: {e}")
            raise OllamaConnectionError(
                f"Request to Ollama timed out after {timeout} seconds: {e}"
            ) from e
        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, 'status_code', 'unknown')
            self.logger.error(f"HTTP error {status_code}: {e}")
            raise OllamaAPIError(
                f"Ollama API returned error {status_code}: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise OllamaConnectionError(f"Request to Ollama failed: {e}") from e

    def generate_structured(
        self,
        user_prompt: str,
        system_prompt: str,
        format_schema: Dict[str, Any],
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a structured response using Ollama's structured outputs feature.

        This uses the /api/chat endpoint with a JSON schema format constraint.

        Args:
            user_prompt: The user's prompt.
            system_prompt: The system prompt/instructions.
            format_schema: JSON schema defining the expected output structure.
            stream: Whether to stream the response (default: False for structured).

        Returns:
            Parsed JSON response matching the schema.

        Raises:
            OllamaConnectionError: If connection fails.
            OllamaAPIError: If API returns an error or response doesn't match schema.

        Example:
            >>> schema = {
            ...     "type": "object",
            ...     "properties": {
            ...         "command": {"type": "string"},
            ...         "thinking": {"type": "string"}
            ...     }
            ... }
            >>> response = client.generate_structured(
            ...     "check disk usage",
            ...     "You are a helpful assistant",
            ...     schema
            ... )
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if is_debug_mode():
            self.logger.debug("=" * 80)
            self.logger.debug("GENERATE STRUCTURED")
            self.logger.debug("=" * 80)
            self.logger.debug("SYSTEM PROMPT:")
            self.logger.debug(system_prompt)
            self.logger.debug("-" * 80)
            self.logger.debug("USER PROMPT:")
            self.logger.debug(user_prompt)
            if format_schema:
                self.logger.debug("-" * 80)
                self.logger.debug("FORMAT SCHEMA:")
                self.logger.debug(json.dumps(format_schema, indent=2))
            self.logger.debug("=" * 80)

        response = self._make_chat_request(
            messages=messages,
            stream=stream,
            format_schema=format_schema,
        )

        content = ""
        try:
            if stream:
                # For streaming, collect all chunks
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                content += data["message"]["content"]
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
                parsed_response = json.loads(content) if content else {}
                if is_debug_mode():
                    self.logger.debug("=" * 80)
                    self.logger.debug("OLLAMA RESPONSE (generate_structured - streaming)")
                    self.logger.debug("=" * 80)
                    self.logger.debug("RAW CONTENT:")
                    self.logger.debug(content)
                    self.logger.debug("-" * 80)
                    self.logger.debug("PARSED RESPONSE:")
                    self.logger.debug(json.dumps(parsed_response, indent=2))
                    self.logger.debug("=" * 80)
                return parsed_response
            else:
                data = response.json()
                content = data.get("message", {}).get("content", "")
                if not content:
                    raise OllamaAPIError("Empty response from Ollama")
                parsed_response = json.loads(content)
                if is_debug_mode():
                    self.logger.debug("=" * 80)
                    self.logger.debug("OLLAMA RESPONSE (generate_structured - non-streaming)")
                    self.logger.debug("=" * 80)
                    self.logger.debug("RAW CONTENT:")
                    self.logger.debug(content)
                    self.logger.debug("-" * 80)
                    self.logger.debug("PARSED RESPONSE:")
                    self.logger.debug(json.dumps(parsed_response, indent=2))
                    self.logger.debug("=" * 80)
                return parsed_response
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse structured response: {e}")
            if is_debug_mode():
                self.logger.debug("=" * 80)
                self.logger.debug("OLLAMA RESPONSE ERROR")
                self.logger.debug("=" * 80)
                self.logger.debug(f"Error: {e}")
                if content:
                    self.logger.debug("Failed to parse content:")
                    self.logger.debug(content)
                self.logger.debug("=" * 80)
            raise OllamaAPIError(
                f"Response does not match expected schema: {e}"
            ) from e

    def generate_with_system_prompt_structured(
        self,
        user_prompt: str,
        system_prompt: str,
        format_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a structured response with system prompt using chat API.

        Convenience method that combines system prompt with structured outputs.

        Args:
            user_prompt: The user's prompt.
            system_prompt: The system prompt/instructions.
            format_schema: JSON schema defining the expected output structure.

        Returns:
            Parsed JSON response matching the schema.

        Raises:
            OllamaConnectionError: If connection fails.
            OllamaAPIError: If API returns an error.
        """
        return self.generate_structured(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            format_schema=format_schema,
            stream=False,
        )

    def generate_chat(
        self,
        messages: list[Dict[str, str]],
        stream: bool = True,
    ) -> Iterator[str]:
        """
        Generate a response using the chat API with conversation history.

        Args:
            messages: List of message dicts with 'role' ('user' or 'assistant') and 'content'.
            stream: Whether to stream the response.

        Yields:
            Response chunks as strings.

        Raises:
            OllamaConnectionError: If connection fails.
            OllamaAPIError: If API returns an error.

        Example:
            >>> messages = [
            ...     {"role": "user", "content": "What is Linux?"},
            ...     {"role": "assistant", "content": "Linux is an operating system..."},
            ...     {"role": "user", "content": "Tell me more about it"}
            ... ]
            >>> for chunk in client.generate_chat(messages):
            ...     print(chunk, end='')
        """
        response = self._make_chat_request(messages=messages, stream=stream)

        full_response = ""
        if stream:
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            chunk = data["message"]["content"]
                            full_response += chunk
                            yield chunk
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Failed to parse response line: {e}")
                        continue
            if is_debug_mode():
                self.logger.debug("=" * 80)
                self.logger.debug("OLLAMA RESPONSE (generate_chat - streaming)")
                self.logger.debug("=" * 80)
                self.logger.debug("FULL RESPONSE:")
                self.logger.debug(full_response)
                self.logger.debug("=" * 80)
        else:
            try:
                data = response.json()
                if "message" in data and "content" in data["message"]:
                    full_response = data["message"]["content"]
                    if is_debug_mode():
                        self.logger.debug("=" * 80)
                        self.logger.debug("OLLAMA RESPONSE (generate_chat - non-streaming)")
                        self.logger.debug("=" * 80)
                        self.logger.debug("FULL RESPONSE:")
                        self.logger.debug(full_response)
                        self.logger.debug("=" * 80)
                    yield full_response
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse Ollama response: {e}")
                raise OllamaAPIError(f"Failed to parse Ollama response: {e}") from e

    def test_connection(self) -> bool:
        """
        Test connection to Ollama API.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            # Use a simple test prompt
            response = self._make_request("test", stream=False, timeout=5)
            success = response.status_code == 200
            if success:
                self.logger.debug("Connection test successful")
            else:
                self.logger.warning(f"Connection test returned status {response.status_code}")
            return success
        except Exception as e:
            self.logger.warning(f"Connection test failed: {e}")
            return False

