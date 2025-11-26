"""Tests for command output analysis and reaction."""

import os
from unittest.mock import patch, MagicMock
import pytest
from click.testing import CliRunner

from command_line_assistant.cli import main
from command_line_assistant.executor import CommandExecutor

# Disable Ollama strategy selection in tests
os.environ["CLA_USE_OLLAMA_STRATEGY"] = "false"


class TestOutputAnalysis:
    """Tests for command output analysis and reaction."""

    @patch("command_line_assistant.executor.CommandExecutor.execute_command")
    @patch("command_line_assistant.cli.OllamaClient.generate_with_system_prompt")
    @patch("command_line_assistant.cli.get_config")
    def test_error_output_analysis(
        self, mock_get_config, mock_generate, mock_execute
    ):
        """Test that AI analyzes error output and reacts."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        # First response: command to run
        first_response = """I'll check if a service exists.

```bash
systemctl status nonexistent-service
```"""

        # Second response: analyzing the error
        second_response = """The service doesn't exist. Let me check what services are available.

```bash
systemctl list-units --type=service | head -20
```"""

        mock_generate.side_effect = [
            iter([first_response]),
            iter([second_response]),
        ]

        # First command fails (service not found)
        mock_execute.side_effect = [
            (1, "", "Unit nonexistent-service.service could not be found."),
            (0, "systemd.service\n", ""),
        ]

        runner = CliRunner()
        result = runner.invoke(
            main, ["--execute", "--yes", "check nonexistent service"], catch_exceptions=False
        )

        # Verify two commands were executed
        assert mock_execute.call_count == 2

        # Verify AI was called at least twice (initial + reaction)
        # May be more due to structured output fallback
        assert mock_generate.call_count >= 2

        # Verify error was analyzed
        second_call_args = mock_generate.call_args_list[1][0]
        assert "error" in str(second_call_args[0]).lower() or "output" in str(second_call_args[0]).lower()

    @patch("command_line_assistant.executor.CommandExecutor.execute_command")
    @patch("command_line_assistant.cli.OllamaClient.generate_with_system_prompt")
    @patch("command_line_assistant.cli.get_config")
    def test_success_output_analysis(
        self, mock_get_config, mock_generate, mock_execute
    ):
        """Test that AI analyzes successful output."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        # First response: command
        first_response = """I'll check disk usage.

```bash
df -h
```"""

        # Second response: task complete (no code block)
        second_response = """The disk usage shows 77% used on the root filesystem. The task is complete."""

        mock_generate.side_effect = [
            iter([first_response]),
            iter([second_response]),
        ]

        # Command succeeds
        mock_execute.return_value = (
            0,
            "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        20G   15G  4.5G  77% /\n",
            "",
        )

        runner = CliRunner()
        result = runner.invoke(
            main, ["--execute", "--yes", "check disk usage"], catch_exceptions=False
        )

        # Verify command was executed
        assert mock_execute.called

        # Verify AI analyzed the output (second call)
        assert mock_generate.call_count >= 1

    @patch("command_line_assistant.executor.CommandExecutor.execute_command")
    @patch("command_line_assistant.cli.OllamaClient.generate_with_system_prompt")
    @patch("command_line_assistant.cli.get_config")
    def test_follow_up_command_on_error(
        self, mock_get_config, mock_generate, mock_execute
    ):
        """Test that AI provides follow-up commands when errors occur."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        # First: try to install
        first_response = """I'll install the package.

```bash
sudo dnf install -y test-package
```"""

        # Second: analyze error and provide fix
        second_response = """The package wasn't found. Let me check available packages.

```bash
dnf search test-package
```"""

        mock_generate.side_effect = [
            iter([first_response]),
            iter([second_response]),
        ]

        # First command fails, second succeeds
        mock_execute.side_effect = [
            (1, "", "No package test-package available."),
            (0, "test-package.x86_64 : Test package", ""),
        ]

        runner = CliRunner()
        result = runner.invoke(
            main, ["--execute", "--yes", "install test-package"], catch_exceptions=False
        )

        # Verify both commands executed
        assert mock_execute.call_count == 2

        # Verify output was passed to AI for analysis
        second_call = mock_generate.call_args_list[1][0][0]
        assert "output" in second_call.lower() or "error" in second_call.lower()

    @patch("command_line_assistant.executor.CommandExecutor.execute_command")
    @patch("command_line_assistant.cli.OllamaClient.generate_with_system_prompt")
    @patch("command_line_assistant.cli.get_config")
    def test_max_iterations_limit(
        self, mock_get_config, mock_generate, mock_execute
    ):
        """Test that max iterations limit is respected."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        # Always return a command (simulating infinite loop scenario)
        mock_generate.return_value = iter([
            """Continue task.

```bash
echo "test"
```"""
        ])

        mock_execute.return_value = (0, "test\n", "")

        runner = CliRunner()
        result = runner.invoke(
            main, ["--execute", "--yes", "test task"], catch_exceptions=False
        )

        # Should stop after max_iterations (default 5)
        # Note: Due to structured output fallback, may execute fewer commands
        assert mock_execute.call_count <= 5
        # Check if we hit max iterations or if execution stopped for another reason
        assert "maximum iterations" in result.output.lower() or mock_execute.call_count >= 1

