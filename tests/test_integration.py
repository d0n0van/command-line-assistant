"""Integration tests for command-line-assistant."""

import os
import subprocess
from unittest.mock import patch, MagicMock
import pytest
from click.testing import CliRunner

from command_line_assistant.cli import main, process_query_with_execution
from command_line_assistant.client import OllamaClient
from command_line_assistant.executor import CommandExecutor

# Disable Ollama strategy selection in tests
os.environ["CLA_USE_OLLAMA_STRATEGY"] = "false"


class TestDiskUsageIntegration:
    """Integration tests for disk usage query."""

    @patch("command_line_assistant.executor.CommandExecutor.execute_command")
    @patch("command_line_assistant.cli.OllamaClient.generate_with_system_prompt")
    @patch("command_line_assistant.cli.get_config")
    def test_disk_usage_query_with_execution(
        self, mock_get_config, mock_generate, mock_execute
    ):
        """Test full flow of disk usage query with command execution."""
        # Setup mocks
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        # Mock AI response for disk usage query
        ai_response = """I'll check the disk usage for you using the 'df -h' command, which shows filesystem disk space usage in human-readable format.

```bash
df -h
```"""

        mock_generate.return_value = iter([ai_response])

        # Mock command execution
        mock_execute.return_value = (
            0,  # return code
            "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        20G   15G  4.5G  77% /\n",  # stdout
            "",  # stderr
        )

        # Run the integration test
        runner = CliRunner()
        result = runner.invoke(
            main, ["--execute", "--yes", "check disk usage"], catch_exceptions=False
        )

        # Verify AI was called with system prompt
        assert mock_generate.called
        # Check first call (may have multiple calls due to structured output fallback)
        first_call = mock_generate.call_args_list[0] if mock_generate.call_args_list else mock_generate.call_args
        if isinstance(first_call, tuple):
            call_args = first_call[0]
        else:
            call_args = first_call[0]
        # System prompt should contain platform info or "Bash Automation"
        assert "Bash Automation" in call_args[1] or "Linux" in call_args[1]
        # First call should contain the original query (or it may be in a follow-up call)
        # Check all calls for the original query
        found_query = False
        for call in mock_generate.call_args_list:
            if "check disk usage" in str(call[0][0]).lower() or "disk" in str(call[0][0]).lower():
                found_query = True
                break
        # If not found in calls, it might be in the first iteration before follow-up
        assert found_query or "check disk usage" in str(call_args[0]).lower() or "disk" in str(call_args[0]).lower()

        # Verify command was extracted and executed
        assert mock_execute.called
        execute_call = mock_execute.call_args[0]
        assert "df -h" in execute_call[0]

        # Verify output contains expected elements
        assert "df -h" in result.output or "Executing" in result.output
        assert "Filesystem" in result.output or "successfully" in result.output.lower()

    @patch("command_line_assistant.executor.CommandExecutor.execute_command")
    def test_disk_usage_command_extraction(self, mock_execute):
        """Test command extraction from AI response."""
        executor = CommandExecutor()

        # Simulate AI response with bash code block
        ai_response = """I'll check disk usage.

```bash
df -h
```"""

        # Extract command
        command = executor.extract_command(ai_response)
        assert command == "df -h"

        # Extract thinking text
        thinking = executor.format_thinking(ai_response)
        assert "I'll check disk usage" in thinking
        assert "df -h" not in thinking  # Command should be removed

    @patch("subprocess.run")
    def test_disk_usage_command_execution(self, mock_subprocess):
        """Test actual command execution."""
        executor = CommandExecutor()

        # Mock subprocess result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        20G   15G  4.5G  77% /\n"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # Execute command
        returncode, stdout, stderr = executor.execute_command(
            "df -h", confirm=False, show_output=True
        )

        # Verify execution
        assert returncode == 0
        assert "Filesystem" in stdout
        assert mock_subprocess.called
        call_args = mock_subprocess.call_args
        assert call_args[1]["shell"] is True
        assert call_args[1]["timeout"] == 30

    def test_disk_usage_thinking_extraction(self):
        """Test that thinking text is properly extracted."""
        executor = CommandExecutor()

        # Full AI response
        full_response = """I'll check the disk usage for you using the 'df -h' command, which shows filesystem disk space usage in human-readable format.

```bash
df -h
```"""

        thinking = executor.format_thinking(full_response)
        assert "I'll check the disk usage" in thinking
        # Code block markers should be removed
        assert "```bash" not in thinking
        assert "```" not in thinking
        # The actual command in code block should be removed, but mention in text is OK
        # Check that the standalone command line is not present
        lines = thinking.split('\n')
        assert not any(line.strip() == "df -h" for line in lines)

    @patch("command_line_assistant.cli.OllamaClient.generate_with_system_prompt")
    @patch("command_line_assistant.cli.get_config")
    def test_disk_usage_no_code_block(self, mock_get_config, mock_generate):
        """Test behavior when AI doesn't provide a code block (safety/uncertainty)."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        # AI response asking for clarification (no code block)
        ai_response = """I am not sure which disk usage information you need. Do you want to see:
- Overall filesystem usage (df -h)
- Directory size (du -sh)
- Specific directory details

Please clarify what you'd like to check."""

        mock_generate.return_value = iter([ai_response])

        client = OllamaClient(mock_config)

        runner = CliRunner()
        result = runner.invoke(
            main, ["--execute", "disk usage"], catch_exceptions=False
        )

        # Should show the AI response but not execute anything
        assert "not sure" in result.output or "clarify" in result.output.lower()
        # Should not have execution-related output
        assert "Executing:" not in result.output

    @patch("command_line_assistant.executor.CommandExecutor.execute_command")
    @patch("command_line_assistant.cli.OllamaClient.generate_with_system_prompt")
    @patch("command_line_assistant.cli.get_config")
    def test_disk_usage_multi_line_command(
        self, mock_get_config, mock_generate, mock_execute
    ):
        """Test handling of multi-line commands."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        # AI response with multiple commands
        ai_response = """I'll check disk usage and then show directory sizes.

```bash
df -h
du -sh /home
```"""

        mock_generate.return_value = iter([ai_response])
        mock_execute.return_value = (0, "output", "")

        client = OllamaClient(mock_config)

        runner = CliRunner()
        result = runner.invoke(
            main, ["--execute", "--yes", "check disk usage"], catch_exceptions=False
        )

        # Verify multi-line command was joined
        assert mock_execute.called
        execute_call = mock_execute.call_args[0]
        # Should be joined with &&
        assert "df -h" in execute_call[0]
        assert "du -sh" in execute_call[0]
        assert "&&" in execute_call[0]

    @patch("command_line_assistant.executor.CommandExecutor.execute_command")
    @patch("command_line_assistant.cli.OllamaClient.generate_with_system_prompt")
    @patch("command_line_assistant.cli.get_config")
    def test_disk_usage_with_sudo(
        self, mock_get_config, mock_generate, mock_execute
    ):
        """Test disk usage command with sudo."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        # AI response with sudo command
        ai_response = """I'll check disk usage with detailed information.

```bash
sudo df -h
```"""

        mock_generate.return_value = iter([ai_response])
        mock_execute.return_value = (0, "Filesystem output", "")

        client = OllamaClient(mock_config)

        runner = CliRunner()
        result = runner.invoke(
            main, ["--execute", "--yes", "check disk usage"], catch_exceptions=False
        )

        # Verify sudo command was extracted
        assert mock_execute.called
        execute_call = mock_execute.call_args[0]
        assert "sudo df -h" in execute_call[0] or "df -h" in execute_call[0]

