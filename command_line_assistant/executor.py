"""Command execution module for command-line-assistant."""

import re
import subprocess
from typing import Optional, Tuple

from command_line_assistant.logger import get_logger
from command_line_assistant.sanitizer import InputSanitizer


class CommandExecutor:
    """Handles command execution with safety checks."""

    # Dangerous commands that should not be executed
    DANGEROUS_COMMANDS = [
        "rm -rf /",
        "rm -rf ~",
        "rm -rf /*",
        "dd if=",
        "mkfs",
        "fdisk",
        "format",
        ":(){ :|:& };:",
        "chmod -R 777 /",
        "chown -R root:root /",
    ]

    # Commands that require confirmation
    CONFIRMATION_REQUIRED = [
        "rm ",
        "delete",
        "uninstall",
        "kill",
        "shutdown",
        "reboot",
    ]

    def __init__(self):
        """Initialize command executor."""
        self.logger = get_logger(f"{__name__}.CommandExecutor")
        self.sanitizer = InputSanitizer()

    def extract_command(self, text: str) -> Optional[str]:
        """
        Extract command from AI response.

        Primary format: ```bash ... ``` code blocks (as per system prompt).
        Falls back to other formats for compatibility.

        Args:
            text: The AI response text.

        Returns:
            Extracted command or None if no command found.
        """
        # Pattern 1: ```bash\ncommand\n``` (PRIMARY - matches system prompt format)
        # This is the strict format expected by the automation agent
        pattern1 = r"```bash\s*\n(.*?)\n```"
        match = re.search(pattern1, text, re.DOTALL)
        if match:
            cmd = match.group(1).strip()
            if cmd:
                # Remove any leading/trailing whitespace and newlines
                cmd = re.sub(r'^\s+|\s+$', '', cmd, flags=re.MULTILINE)
                # Handle multi-line commands (join with && or ;)
                lines = [line.strip() for line in cmd.split('\n') if line.strip()]
                if lines:
                    # Join multiple commands with && for sequential execution
                    return ' && '.join(lines)

        # Pattern 2: ```sh\ncommand\n``` (fallback for sh blocks)
        pattern2 = r"```sh\s*\n(.*?)\n```"
        match = re.search(pattern2, text, re.DOTALL)
        if match:
            cmd = match.group(1).strip()
            if cmd:
                cmd = re.sub(r'^\s+|\s+$', '', cmd, flags=re.MULTILINE)
                lines = [line.strip() for line in cmd.split('\n') if line.strip()]
                if lines:
                    return ' && '.join(lines)

        # Pattern 3: Generic code block ```...``` (fallback)
        pattern3 = r"```(?:[a-z]+)?\s*\n(.*?)\n```"
        match = re.search(pattern3, text, re.DOTALL)
        if match:
            cmd = match.group(1).strip()
            if cmd:
                cmd = re.sub(r'^\s+|\s+$', '', cmd, flags=re.MULTILINE)
                lines = [line.strip() for line in cmd.split('\n') if line.strip()]
                if lines:
                    return ' && '.join(lines)

        # Pattern 4: EXECUTE: command (legacy format)
        pattern4 = r"EXECUTE:\s*(.+?)(?:\n|$)"
        match = re.search(pattern4, text, re.IGNORECASE)
        if match:
            cmd = match.group(1).strip()
            if cmd:
                return cmd

        # No code block found - this is expected when AI asks for clarification
        # or refuses to execute dangerous commands
        return None

    def is_dangerous(self, command: str) -> bool:
        """
        Check if a command is dangerous.

        Args:
            command: The command to check.

        Returns:
            True if command is dangerous.
        """
        command_lower = command.lower()
        for dangerous in CommandExecutor.DANGEROUS_COMMANDS:
            if dangerous.lower() in command_lower:
                return True
        return False

    def requires_confirmation(self, command: str) -> bool:
        """
        Check if a command requires confirmation.

        Args:
            command: The command to check.

        Returns:
            True if command requires confirmation.
        """
        command_lower = command.lower()
        for pattern in CommandExecutor.CONFIRMATION_REQUIRED:
            if pattern.lower() in command_lower:
                return True
        return False

    def has_sudo(self, command: str) -> bool:
        """
        Check if command contains sudo.

        Args:
            command: The command to check.

        Returns:
            True if command contains sudo.
        """
        # Check for sudo at the start or after && or ;
        return bool(re.search(r'(^|\s|&&|;)\s*sudo\s+', command))

    def strip_sudo(self, command: str) -> str:
        """
        Strip sudo from command.

        Args:
            command: The command to process.

        Returns:
            Command with sudo removed.
        """
        # Remove sudo from the beginning or after && or ;
        # Handle: "sudo cmd", "&& sudo cmd", "; sudo cmd"
        # Preserve spaces after && and ;
        command = re.sub(r'(^|\s|&&\s*|;\s*)\s*sudo\s+', r'\1', command)
        # Clean up any double spaces but preserve single spaces
        command = re.sub(r'  +', ' ', command).strip()
        return command

    def execute_command(
        self, command: str, confirm: bool = True, show_output: bool = True, allow_sudo: bool = False, timeout: int = 30
    ) -> Tuple[int, str, str]:
        """
        Execute a shell command.

        Args:
            command: The command to execute.
            confirm: Whether to require confirmation for certain commands.
            show_output: Whether to show command output.
            allow_sudo: Whether to allow sudo commands (default: False, sudo is stripped).
            timeout: Command timeout in seconds. Use -1 for infinite timeout.

        Returns:
            Tuple of (return_code, stdout, stderr).

        Raises:
            ValueError: If command is dangerous, invalid, or requires confirmation.
            TimeoutError: If command times out.
            RuntimeError: If command execution fails.
        """
        # Input validation
        if not command or not isinstance(command, str):
            raise ValueError("Command must be a non-empty string")
        
        # Sanitize command input
        try:
            command = self.sanitizer.sanitize_command(command)
        except ValueError as e:
            self.logger.warning(f"Command sanitization failed: {e}")
            raise ValueError(f"Invalid command: {e}") from e
        
        # Handle sudo removal if not allowed (default behavior)
        original_command = command
        if not allow_sudo:
            if self.has_sudo(command):
                command = self.strip_sudo(command)
                self.logger.debug(f"Stripped sudo from command: {original_command} -> {command}")
        
        if self.is_dangerous(command):
            self.logger.warning(f"Blocked dangerous command: {command}")
            raise ValueError(f"Dangerous command detected: {command}")

        if confirm and self.requires_confirmation(command):
            self.logger.debug(f"Command requires confirmation: {command}")
            raise ValueError(
                f"Command requires confirmation: {command}. "
                "Use --yes flag to execute without confirmation."
            )

        try:
            self.logger.debug(f"Executing command: {command} (timeout={timeout})")
            # Use shell=True for flexibility, but be careful
            # timeout=None means infinite timeout (for timeout=-1)
            timeout_value = None if timeout == -1 else timeout
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_value,
            )
            self.logger.debug(f"Command completed with return code {result.returncode}")
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as e:
            timeout_msg = "infinite" if timeout == -1 else f"{timeout} seconds"
            self.logger.error(f"Command timed out after {timeout_msg}: {command}")
            raise TimeoutError(f"Command timed out after {timeout_msg}: {command}") from e
        except Exception as e:
            self.logger.error(f"Failed to execute command: {e}")
            raise RuntimeError(f"Failed to execute command: {e}") from e

    def format_thinking(self, text: str) -> str:
        """
        Format thinking process from AI response.

        Extracts and formats the conversational text, removing code blocks.
        This is the "human talk" part that should be shown to the user.

        Args:
            text: The full AI response.

        Returns:
            Formatted thinking/conversational text.
        """
        # Remove all code blocks (```bash ... ```, ```sh ... ```, etc.)
        text = re.sub(r"```(?:[a-z]+)?\s*\n.*?\n```", "", text, flags=re.DOTALL)
        # Remove EXECUTE: lines (legacy format)
        text = re.sub(r"EXECUTE:\s*.+", "", text, flags=re.IGNORECASE)
        # Clean up extra whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove any remaining markdown artifacts
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # Remove bold markers
        text = re.sub(r"\*([^*]+)\*", r"\1", text)  # Remove italic markers
        return text.strip()

