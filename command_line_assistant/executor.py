"""Command execution module for command-line-assistant."""

import re
import subprocess
import json
from typing import Optional, Tuple, List, Dict

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
        Extract a single command from AI response.

        Supports:
        1. Structured JSON format with "commands" array (primary)
        2. Code blocks (```bash ... ```) for backward compatibility
        3. Legacy EXECUTE: format

        Args:
            text: The AI response text.

        Returns:
            Extracted command or None if no command found.
        """
        # First, try to parse as structured JSON (primary format)
        data = self._parse_json_commands(text)
        if data and isinstance(data, dict) and "commands" in data:
            commands_array = data.get("commands", [])
            if isinstance(commands_array, list) and len(commands_array) > 0:
                # Return first command from JSON
                cmd_obj = commands_array[0]
                if isinstance(cmd_obj, dict):
                    cmd_text = cmd_obj.get("command", "").strip()
                    if cmd_text:
                        return cmd_text
        
        # Fallback to code block patterns for backward compatibility
        # Pattern 1: ```bash\ncommand\n``` (fallback - matches old system prompt format)
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

    def _parse_json_commands(self, text: str) -> Optional[Dict]:
        """
        Helper method to parse JSON and extract commands data.
        
        Args:
            text: The text to parse.
            
        Returns:
            Parsed JSON dict if valid, None otherwise.
        """
        # Look for JSON code blocks first
        json_block_pattern = r'```(?:json)?\s*\n(\{.*?\})\n```'
        json_block_match = re.search(json_block_pattern, text, re.DOTALL)
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON in plain text (without code blocks)
        json_start = text.find('{')
        if json_start != -1:
            brace_count = 0
            json_end = -1
            for i in range(json_start, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break
            
            if json_end != -1:
                try:
                    return json.loads(text[json_start:json_end])
                except (json.JSONDecodeError, ValueError):
                    pass
        
        return None

    def extract_thinking(self, text: str) -> str:
        """
        Extract thinking/reasoning from structured JSON response.
        
        Args:
            text: The AI response text.
            
        Returns:
            Thinking text or empty string if not found.
        """
        data = self._parse_json_commands(text)
        if data and isinstance(data, dict) and "thinking" in data:
            thinking = data.get("thinking", "").strip()
            return thinking
        return ""

    def extract_commands_with_descriptions(self, text: str) -> List[Dict[str, str]]:
        """
        Extract commands with descriptions from structured JSON response.
        
        Args:
            text: The AI response text.
            
        Returns:
            List of dicts with 'command' and 'description' keys.
        """
        result = []
        data = self._parse_json_commands(text)
        
        if data and isinstance(data, dict) and "commands" in data:
            commands_array = data.get("commands", [])
            if isinstance(commands_array, list):
                for cmd_obj in commands_array:
                    if isinstance(cmd_obj, dict):
                        cmd_text = cmd_obj.get("command", "").strip()
                        cmd_desc = cmd_obj.get("description", "").strip()
                        if cmd_text:
                            result.append({
                                "command": cmd_text,
                                "description": cmd_desc or "No description"
                            })
        
        return result

    def extract_all_commands(self, text: str) -> List[str]:
        """
        Extract all commands from AI response.
        
        Looks for:
        1. Structured JSON format with "commands" array
        2. Multiple code blocks (```bash ... ```, ```sh ... ```, etc.)
        3. Numbered commands in text (1. command, 2. command, etc.) with associated code blocks
        
        Args:
            text: The AI response text.
            
        Returns:
            List of extracted commands (may be empty).
        """
        commands = []
        
        # First, try to parse as structured JSON
        data = self._parse_json_commands(text)
        if data and isinstance(data, dict) and "commands" in data:
            commands_array = data.get("commands", [])
            if isinstance(commands_array, list):
                for cmd_obj in commands_array:
                    if isinstance(cmd_obj, dict):
                        cmd_text = cmd_obj.get("command", "").strip()
                        if cmd_text:
                            commands.append(cmd_text)
                if commands:
                    return commands
        
        # First, find all code blocks and check if they're associated with numbered items
        # Pattern to match: "1. text... ```bash\ncommand\n```" or "```bash\ncommand\n```" (standalone)
        code_block_pattern = r"```(bash|sh|cmd|powershell|python)?\s*\n(.*?)\n```"
        code_blocks = list(re.finditer(code_block_pattern, text, re.DOTALL))
        
        if len(code_blocks) > 1:
            # Multiple code blocks found - extract all bash/sh commands
            for match in code_blocks:
                lang = match.group(1) or ""
                cmd = match.group(2).strip()
                
                # Only extract bash/sh commands (Linux commands)
                if lang.lower() in ('bash', 'sh', '') or not lang:
                    if cmd:
                        cmd = re.sub(r'^\s+|\s+$', '', cmd, flags=re.MULTILINE)
                        lines = [line.strip() for line in cmd.split('\n') if line.strip()]
                        if lines:
                            cmd_str = ' && '.join(lines)
                            # Filter out Windows/PowerShell commands
                            if not any(windows_cmd in cmd_str.lower() for windows_cmd in ['powershell', 'get-childitem', 'dir /s', 'for /f', 'cmd.exe']):
                                commands.append(cmd_str)
        
        # If we found multiple Linux commands, return them
        if len(commands) > 1:
            return commands
        
        # Check for numbered items with code blocks
        # Pattern: "1. **Linux/Unix...** ```bash\ncommand\n```"
        numbered_section_pattern = r"(\d+)\.\s+[^\n]*\n(?:[^\n]*\n)?```(bash|sh)?\s*\n(.*?)\n```"
        numbered_sections = list(re.finditer(numbered_section_pattern, text, re.DOTALL | re.IGNORECASE))
        
        if numbered_sections and len(numbered_sections) > 1:
            # Found numbered sections with code blocks
            numbered_commands = []
            for match in numbered_sections:
                lang = match.group(2) or ""
                cmd = match.group(3).strip()
                
                # Only extract bash/sh commands (Linux commands)
                if lang.lower() in ('bash', 'sh', '') or not lang:
                    if cmd:
                        cmd = re.sub(r'^\s+|\s+$', '', cmd, flags=re.MULTILINE)
                        lines = [line.strip() for line in cmd.split('\n') if line.strip()]
                        if lines:
                            cmd_str = ' && '.join(lines)
                            # Filter out Windows/PowerShell commands
                            if not any(windows_cmd in cmd_str.lower() for windows_cmd in ['powershell', 'get-childitem', 'dir /s', 'for /f', 'cmd.exe']):
                                numbered_commands.append(cmd_str)
            
            if numbered_commands:
                return numbered_commands
        
        # Return single command if found, or empty list
        return commands if commands else []

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

