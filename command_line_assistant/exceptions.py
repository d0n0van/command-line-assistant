"""Custom exceptions for command-line-assistant."""


class CommandLineAssistantError(Exception):
    """Base exception for command-line-assistant errors."""

    pass


class ConfigurationError(CommandLineAssistantError):
    """Raised when there's a configuration error."""

    pass


class OllamaConnectionError(CommandLineAssistantError):
    """Raised when unable to connect to Ollama API."""

    pass


class OllamaAPIError(CommandLineAssistantError):
    """Raised when Ollama API returns an error."""

    pass

