"""Input sanitization and validation for command-line-assistant."""

import re
import html
from typing import Optional
from pathlib import Path

from command_line_assistant.logger import get_logger


class InputSanitizer:
    """Sanitizes and validates user input to prevent security issues."""

    # Maximum input length (characters)
    MAX_INPUT_LENGTH = 10000
    MAX_COMMAND_LENGTH = 2000

    # Dangerous patterns that should be blocked
    DANGEROUS_PATTERNS = [
        r'<script\b[^>]*>(.*?)</script>',  # Script tags
        r'javascript:',  # JavaScript protocol
        r'on\w+\s*=',  # Event handlers (onclick, onerror, etc.)
        r'data:text/html',  # Data URLs with HTML
        r'vbscript:',  # VBScript protocol
    ]

    # Control characters that should be removed
    CONTROL_CHARS = re.compile(r'[\x00-\x1f\x7f-\x9f]')

    def __init__(self):
        """Initialize input sanitizer."""
        self.logger = get_logger(f"{__name__}.InputSanitizer")

    def sanitize_query(self, query: str) -> str:
        """
        Sanitize user query input.

        Args:
            query: Raw user input query.

        Returns:
            Sanitized query string.

        Raises:
            ValueError: If input is invalid or too long.
        """
        if not isinstance(query, str):
            raise ValueError("Query must be a string")

        # Check length
        if len(query) > self.MAX_INPUT_LENGTH:
            self.logger.warning(f"Query too long: {len(query)} characters")
            raise ValueError(f"Query too long (max {self.MAX_INPUT_LENGTH} characters)")

        # Strip whitespace
        query = query.strip()

        if not query:
            raise ValueError("Query cannot be empty")

        # Remove control characters
        query = self.CONTROL_CHARS.sub('', query)

        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                self.logger.warning(f"Blocked dangerous pattern in query: {pattern}")
                # Remove the dangerous content instead of raising error
                query = re.sub(pattern, '', query, flags=re.IGNORECASE)

        # Normalize whitespace (multiple spaces to single)
        query = re.sub(r'\s+', ' ', query)

        return query.strip()

    def sanitize_command(self, command: str) -> str:
        """
        Sanitize command string before execution.

        Args:
            command: Raw command string.

        Returns:
            Sanitized command string.

        Raises:
            ValueError: If command is invalid or too long.
        """
        if not isinstance(command, str):
            raise ValueError("Command must be a string")

        # Check length
        if len(command) > self.MAX_COMMAND_LENGTH:
            self.logger.warning(f"Command too long: {len(command)} characters")
            raise ValueError(f"Command too long (max {self.MAX_COMMAND_LENGTH} characters)")

        # Strip whitespace
        command = command.strip()

        if not command:
            raise ValueError("Command cannot be empty")

        # Remove control characters (except newlines and tabs which might be needed)
        # Keep \n and \t, remove others
        command = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', command)

        # Remove null bytes
        command = command.replace('\x00', '')

        # Normalize whitespace (but preserve intentional spacing)
        # Replace multiple spaces with single space, but keep newlines
        lines = command.split('\n')
        sanitized_lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in lines]
        command = '\n'.join(sanitized_lines)

        return command.strip()

    def sanitize_path(self, path: str) -> Optional[str]:
        """
        Sanitize file path input.

        Args:
            path: Raw path string.

        Returns:
            Sanitized path or None if invalid.

        Raises:
            ValueError: If path contains dangerous patterns.
        """
        if not isinstance(path, str):
            raise ValueError("Path must be a string")

        path = path.strip()

        if not path:
            return None

        # Remove control characters
        path = self.CONTROL_CHARS.sub('', path)

        # Block path traversal attempts
        dangerous_path_patterns = [
            r'\.\./',  # Parent directory traversal
            r'\.\.\\',  # Windows parent directory
            r'//',  # Multiple slashes (potential issues)
            r'~',  # Home directory (could be dangerous)
        ]

        for pattern in dangerous_path_patterns:
            if re.search(pattern, path):
                self.logger.warning(f"Blocked dangerous path pattern: {pattern}")
                raise ValueError(f"Invalid path: contains dangerous pattern")

        # Normalize path
        try:
            normalized = Path(path).resolve()
            return str(normalized)
        except (ValueError, OSError) as e:
            self.logger.warning(f"Invalid path: {e}")
            raise ValueError(f"Invalid path: {e}") from e

    def sanitize_config_value(self, value: str, value_type: str = "string") -> str:
        """
        Sanitize configuration value.

        Args:
            value: Raw configuration value.
            value_type: Type of value ('string', 'url', 'number').

        Returns:
            Sanitized value.

        Raises:
            ValueError: If value is invalid.
        """
        if not isinstance(value, str):
            raise ValueError("Config value must be a string")

        value = value.strip()

        if value_type == "url":
            # URL validation
            if not re.match(r'^https?://', value, re.IGNORECASE):
                raise ValueError("URL must start with http:// or https://")
            # Remove control characters
            value = self.CONTROL_CHARS.sub('', value)
        elif value_type == "number":
            # Number validation (for temperature, etc.)
            try:
                float(value)
            except ValueError:
                raise ValueError(f"Invalid number: {value}")
        else:
            # String value - remove control characters
            value = self.CONTROL_CHARS.sub('', value)

        return value

    def sanitize_ai_response(self, response: str) -> str:
        """
        Sanitize AI response before parsing.

        Args:
            response: Raw AI response text.

        Returns:
            Sanitized response.
        """
        if not isinstance(response, str):
            return ""

        # Remove null bytes
        response = response.replace('\x00', '')

        # Remove most control characters (keep newlines and tabs)
        response = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', response)

        # Limit length
        if len(response) > self.MAX_INPUT_LENGTH * 2:  # Allow longer for AI responses
            self.logger.warning(f"AI response truncated: {len(response)} characters")
            response = response[:self.MAX_INPUT_LENGTH * 2]

        return response

    def validate_json_safe(self, text: str) -> bool:
        """
        Check if text is safe for JSON parsing.

        Args:
            text: Text to validate.

        Returns:
            True if safe, False otherwise.
        """
        if not isinstance(text, str):
            return False

        # Check for null bytes
        if '\x00' in text:
            return False

        # Check for extremely long strings
        if len(text) > self.MAX_INPUT_LENGTH * 2:
            return False

        return True

