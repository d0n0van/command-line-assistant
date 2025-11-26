"""CLI interface for command-line-assistant."""

import re
import sys
from pathlib import Path
from typing import Dict, Optional

import click

# Try to import readline for history support
try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    # readline not available (e.g., on Windows without pyreadline)
    READLINE_AVAILABLE = False
    readline = None

from command_line_assistant import __version__
from command_line_assistant.client import OllamaClient
from command_line_assistant.config import get_config, ConfigurationError
from command_line_assistant.executor import CommandExecutor
from command_line_assistant.prompt_builder import PromptBuilder
from command_line_assistant.platform_detector import PlatformDetector
from command_line_assistant.exceptions import (
    OllamaConnectionError,
    OllamaAPIError,
    CommandLineAssistantError,
)
from command_line_assistant.logger import get_logger, set_debug_mode, is_debug_mode
from command_line_assistant.schemas import get_command_response_schema
from command_line_assistant.sanitizer import InputSanitizer
from command_line_assistant.query_evaluator import QueryEvaluator
from command_line_assistant.context_collector import ContextCollector


def print_response(response: str) -> None:
    """Print response to stdout."""
    click.echo(response, nl=False)


def print_error(message: str) -> None:
    """Print error message to stderr."""
    click.echo(click.style(f"Error: {message}", fg="red"), err=True)


def print_info(message: str) -> None:
    """Print info message."""
    click.echo(click.style(message, fg="blue"))


def print_success(message: str) -> None:
    """Print success message."""
    click.echo(click.style(message, fg="green"))


def print_command(command: str) -> None:
    """Print command in a highlighted format."""
    click.echo(click.style(f"\n→ Executing: {command}", fg="yellow", bold=True))


def print_thinking(text: str) -> None:
    """Print thinking process."""
    if text.strip():
        click.echo(click.style("\n💭 Thinking:", fg="cyan", bold=True))
        click.echo(text)


def interactive_mode(client: OllamaClient, execute: bool = False, yes: bool = False, allow_sudo: bool = False, max_iterations: int = 5, timeout: int = 30) -> None:
    """Run interactive mode with conversation history."""
    click.echo("Command Line Assistant (Ollama)")
    if execute:
        click.echo(click.style("Command execution mode enabled", fg="yellow"))
        if not allow_sudo:
            click.echo(click.style("Sudo commands disabled (default)", fg="yellow"))
        else:
            click.echo(click.style("Sudo commands enabled", fg="yellow"))
        if max_iterations == -1:
            click.echo(click.style("Max iterations: infinite", fg="yellow"))
        else:
            click.echo(click.style(f"Max iterations: {max_iterations}", fg="yellow"))
        if timeout == -1:
            click.echo(click.style("Command timeout: infinite", fg="yellow"))
        else:
            click.echo(click.style(f"Command timeout: {timeout} seconds", fg="yellow"))
    click.echo("Type 'quit', 'exit', or 'q' to exit (or press Ctrl+C)")
    click.echo("Type 'clear' to clear conversation history")
    click.echo("=" * 50)

    # Set up readline history if available
    history_file = None
    if READLINE_AVAILABLE:
        try:
            # Set up history file
            history_file = Path.home() / ".config" / "command-line-assistant" / "history"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Load history if it exists
            if history_file.exists():
                try:
                    readline.read_history_file(str(history_file))
                except (IOError, OSError):
                    pass  # Ignore errors loading history
            
            # Set history size (default is usually -1 for unlimited, but we'll limit to 1000)
            readline.set_history_length(1000)
            
            # Enable tab completion (basic - can be enhanced later)
            readline.parse_and_bind("tab: complete")
            
            # Arrow keys, Page Up/Down, and other navigation keys should work automatically
            # with readline on Unix-like systems. No additional bindings needed.
        except Exception as e:
            logger = get_logger(__name__)
            logger.debug(f"Failed to set up readline history: {e}")

    sanitizer = InputSanitizer()
    # Maintain conversation history for context
    conversation_history: list[Dict[str, str]] = []
    
    # Add system prompt to conversation history for non-execute mode
    if not execute:
        from command_line_assistant.prompt_builder import PromptBuilder
        prompt_builder = PromptBuilder()
        system_prompt = prompt_builder.build_system_prompt(allow_sudo=allow_sudo)
        conversation_history.append({"role": "system", "content": system_prompt})
    
    while True:
        try:
            # Use input() - Python's input() automatically uses readline if available
            # We've already configured readline above, so history navigation will work
            raw_prompt = input("\n> ").strip()
            
            # Add to readline history if available and not empty
            # Note: readline automatically handles duplicates, so we can just add it
            if READLINE_AVAILABLE and raw_prompt:
                try:
                    readline.add_history(raw_prompt)
                except Exception:
                    pass  # Ignore errors adding to history

            if not raw_prompt:
                continue

            if raw_prompt.lower() in ("quit", "exit", "q"):
                click.echo("Goodbye!")
                break

            # Clear conversation history
            if raw_prompt.lower() == "clear":
                conversation_history = []
                # Re-add system prompt if not in execute mode
                if not execute:
                    from command_line_assistant.prompt_builder import PromptBuilder
                    prompt_builder = PromptBuilder()
                    system_prompt = prompt_builder.build_system_prompt(allow_sudo=allow_sudo)
                    conversation_history.append({"role": "system", "content": system_prompt})
                click.echo(click.style("Conversation history cleared.", fg="green"))
                continue

            # Check for execute/run prefixes
            should_execute_directly = False
            if raw_prompt.lower().startswith("execute:") or raw_prompt.lower().startswith("run:"):
                should_execute_directly = True
                # Extract the query after the prefix
                prompt = raw_prompt.split(":", 1)[1].strip()
            else:
                prompt = raw_prompt

            # Sanitize user input
            try:
                prompt = sanitizer.sanitize_query(prompt)
            except ValueError as e:
                print_error(f"Invalid input: {e}")
                continue

            # Generate and stream response
            click.echo()  # New line before response
            try:
                if execute or should_execute_directly:
                    # For execute mode, we still use the existing process_query_with_execution
                    # which maintains its own context for command execution iterations
                    if is_debug_mode():
                        logger = get_logger(__name__)
                        logger.debug("=" * 80)
                        logger.debug("INTERACTIVE MODE: Execute mode")
                        logger.debug("=" * 80)
                        logger.debug(f"Query: {prompt}")
                        logger.debug(f"Auto-confirm: {yes}")
                        logger.debug(f"Max iterations: {max_iterations}")
                        logger.debug(f"Allow sudo: {allow_sudo}")
                        logger.debug("=" * 80)
                    process_query_with_execution(client, prompt, auto_confirm=yes, max_iterations=max_iterations, allow_sudo=allow_sudo, timeout=timeout)
                    # Add to history after execution
                    conversation_history.append({"role": "user", "content": prompt})
                    # Note: We don't add the full execution output to history to keep it manageable
                    # The execution mode maintains its own context for command iterations
                else:
                    # Evaluate query to determine if local context is needed
                    import os
                    cwd = Path(os.getcwd())
                    if is_debug_mode():
                        logger = get_logger(__name__)
                        logger.debug("=" * 80)
                        logger.debug("INTERACTIVE MODE: Non-execute mode")
                        logger.debug("=" * 80)
                        logger.debug(f"Query: {prompt}")
                        logger.debug(f"Current working directory: {cwd}")
                        logger.debug("=" * 80)
                    use_ollama = os.getenv("CLA_USE_OLLAMA_STRATEGY", "true").lower() == "true"
                    query_evaluator = QueryEvaluator(use_ollama=use_ollama, ollama_client=client)
                    query_context = query_evaluator.evaluate_query(prompt, cwd)
                    
                    # Build prompt builder for context collection
                    prompt_builder = PromptBuilder()
                    
                    # Set environment context
                    shell = os.environ.get("SHELL", "bash")
                    if shell:
                        prompt_builder.record_environment_context("shell", shell.split("/")[-1])
                    prompt_builder.record_environment_context("working_directory", str(cwd))
                    
                    # Collect local context if needed
                    context_attachment = ""
                    detected_language = None
                    if query_context.needs_local_context:
                        logger = get_logger(__name__)
                        logger.info(f"Query needs local context. Target path: {query_context.target_path}")
                        context_collector = ContextCollector()
                        target_path = query_context.target_path or cwd
                        
                        # Get directory tree
                        tree = context_collector.get_directory_tree(target_path, max_depth=4)
                        
                        # Collect context files
                        context_files = context_collector.collect_context_files(target_path)
                        
                        # Detect and record project type from files
                        detected_language = None
                        if "package.json" in context_files:
                            prompt_builder.record_environment_context("project_type", "nodejs")
                            detected_language = "JavaScript/Node.js"
                        elif "pyproject.toml" in context_files or "setup.py" in context_files or "requirements.txt" in context_files:
                            prompt_builder.record_environment_context("project_type", "python")
                            detected_language = "Python"
                        elif "Cargo.toml" in context_files:
                            prompt_builder.record_environment_context("project_type", "rust")
                            detected_language = "Rust"
                        elif "pom.xml" in context_files or "build.gradle" in context_files:
                            prompt_builder.record_environment_context("project_type", "java")
                            detected_language = "Java"
                        elif "go.mod" in context_files:
                            prompt_builder.record_environment_context("project_type", "go")
                            detected_language = "Go"
                        
                        # Format as attachment
                        if tree or context_files or detected_language:
                            context_attachment = "\n\n**⚠️ IMPORTANT - LOCAL CONTEXT PROVIDED:**\n"
                            context_attachment += "You have been given local context about the current project. **YOU MUST USE THIS INFORMATION** to answer questions directly without needing to execute commands first.\n\n"
                            if detected_language:
                                context_attachment += f"**✅ DETECTED PROGRAMMING LANGUAGE:** {detected_language}\n"
                                context_attachment += f"**When asked about the programming language, answer: '{detected_language}' directly in the 'thinking' field with an empty commands array []**\n\n"
                            if tree:
                                context_attachment += f"**Directory structure:**\n{tree}\n\n"
                            if context_files:
                                context_attachment += f"**Relevant files found:** {', '.join(context_files)}\n"
                            context_attachment += "\n**REMEMBER:** If the question can be answered from the context above, answer it directly in the 'thinking' field with an empty commands array []. Only use commands if you need additional information not provided in the context.\n"
                    
                    # Rebuild system prompt with updated context
                    system_prompt = prompt_builder.build_system_prompt(allow_sudo=allow_sudo)
                    system_prompt += f"\n\n**CURRENT WORKING DIRECTORY:** {cwd}\n"
                    if context_attachment:
                        system_prompt += context_attachment
                    
                    # Update system prompt in conversation history
                    # Find and update existing system prompt, or add if not present
                    system_prompt_updated = False
                    for i, msg in enumerate(conversation_history):
                        if msg.get("role") == "system":
                            conversation_history[i] = {"role": "system", "content": system_prompt}
                            system_prompt_updated = True
                            break
                    if not system_prompt_updated:
                        conversation_history.insert(0, {"role": "system", "content": system_prompt})
                    
                    # Add user message to history, with context if available
                    user_message = prompt
                    if context_attachment and detected_language:
                        # For programming language questions, add context directly to user message
                        if "language" in prompt.lower() or "programming" in prompt.lower():
                            user_message = f"{prompt}\n\n{context_attachment}"
                    conversation_history.append({"role": "user", "content": user_message})
                    
                    # Generate response with conversation history
                    if is_debug_mode():
                        logger = get_logger(__name__)
                        logger.debug("=" * 80)
                        logger.debug("INTERACTIVE MODE: Generating response with chat API")
                        logger.debug("=" * 80)
                        logger.debug(f"Conversation history: {len(conversation_history)} messages")
                        for i, msg in enumerate(conversation_history):
                            role = msg.get("role", "unknown")
                            content_preview = msg.get("content", "")[:100]
                            logger.debug(f"  [{i+1}] {role}: {content_preview}...")
                        logger.debug("=" * 80)
                    # Collect full response first without displaying (to parse JSON)
                    full_response = ""
                    for chunk in client.generate_chat(conversation_history):
                        full_response += chunk
                    
                    # Add assistant response to history
                    if full_response:
                        conversation_history.append({"role": "assistant", "content": full_response})
                    
                    # Check if response contains executable commands
                    executor = CommandExecutor()
                    # Try to extract commands with descriptions first (from JSON)
                    commands_with_desc = executor.extract_commands_with_descriptions(full_response)
                    
                    # Extract and display thinking text (if JSON format)
                    thinking_text = executor.extract_thinking(full_response)
                    if thinking_text:
                        print_thinking(thinking_text)
                        click.echo()  # New line after thinking
                    
                    # If no JSON format detected, display the full response as-is
                    if not commands_with_desc and not thinking_text:
                        click.echo(full_response)
                        click.echo()  # New line after response
                    
                    if commands_with_desc:
                        click.echo()  # New line
                        
                        if len(commands_with_desc) > 1:
                            # Multiple commands found - let user choose
                            click.echo(click.style("Multiple commands found:", fg="cyan", bold=True))
                            for i, cmd_info in enumerate(commands_with_desc, 1):
                                desc = cmd_info.get("description", "No description")
                                cmd = cmd_info.get("command", "")
                                # Truncate long commands for display
                                display_cmd = cmd[:60] + "..." if len(cmd) > 60 else cmd
                                click.echo(f"  {i}. {desc}")
                                click.echo(f"     {click.style(display_cmd, fg='yellow')}")
                            
                            click.echo()
                            choice = click.prompt(
                                click.style("Select command to execute (1-{}, or N to skip): ".format(len(commands_with_desc)), fg="yellow", bold=True),
                                type=click.Choice([str(i) for i in range(1, len(commands_with_desc) + 1)] + ['N', 'n'], case_sensitive=False),
                                default='N'
                            )
                            
                            if choice.upper() == 'N':
                                print_info("Command execution skipped.")
                            else:
                                selected_index = int(choice) - 1
                                selected_command = commands_with_desc[selected_index].get("command", "")
                                
                                # Execute the selected command directly
                                click.echo()  # New line
                                executor = CommandExecutor()
                                
                                # Check if command requires confirmation
                                if not yes and executor.requires_confirmation(selected_command):
                                    if not click.confirm(f"⚠️  This command requires confirmation. Execute: {selected_command}?"):
                                        print_info("Command execution cancelled.")
                                        continue
                                
                                # Check for sudo
                                if not allow_sudo and executor.has_sudo(selected_command):
                                    print_error("Sudo commands are not allowed. Use --sudo flag to enable.")
                                    continue
                                
                                # Execute command
                                print_command(selected_command)
                                try:
                                    returncode, stdout, stderr = executor.execute_command(
                                        selected_command,
                                        confirm=False,  # Already checked above
                                        show_output=False,  # We'll display it ourselves
                                        allow_sudo=allow_sudo,
                                        timeout=timeout
                                    )
                                    
                                    # Display output
                                    if stdout:
                                        click.echo(click.style("📤 Command Output (stdout):", fg="blue", bold=True))
                                        click.echo(stdout)
                                    else:
                                        click.echo(click.style("📤 Command Output (stdout): (empty)", fg="blue", dim=True))
                                    
                                    if stderr:
                                        click.echo()  # Blank line before stderr
                                        click.echo(click.style("⚠️  Command Error Output (stderr):", fg="red", bold=True))
                                        click.echo(click.style(stderr, fg="red"), err=True)
                                    
                                    click.echo()  # Blank line after output
                                    click.echo(click.style(f"Return code: {returncode}", fg="cyan"))
                                    
                                    if returncode == 0:
                                        print_success("✓ Command executed successfully")
                                    else:
                                        print_error(f"Command exited with code {returncode}")
                                    
                                    # Add command execution to conversation history and continue
                                    command_result = f"Command executed: {selected_command}\nReturn code: {returncode}\n"
                                    if stdout:
                                        command_result += f"Stdout:\n{stdout}\n"
                                    if stderr:
                                        command_result += f"Stderr:\n{stderr}\n"
                                    
                                    conversation_history.append({"role": "user", "content": f"Execute: {selected_command}"})
                                    conversation_history.append({"role": "assistant", "content": command_result})
                                    
                                    # Continue conversation to answer original question
                                    click.echo()  # New line
                                    click.echo(click.style("Analyzing results...", fg="cyan", dim=True))
                                    
                                    # Generate follow-up response
                                    follow_up_response = ""
                                    for chunk in client.generate_chat(conversation_history):
                                        follow_up_response += chunk
                                        print_response(chunk)
                                    
                                    if follow_up_response:
                                        conversation_history.append({"role": "assistant", "content": follow_up_response})
                                        click.echo()  # New line after response
                                        
                                except ValueError as e:
                                    print_error(str(e))
                                except TimeoutError as e:
                                    print_error(str(e))
                                except RuntimeError as e:
                                    print_error(str(e))
                        elif len(commands_with_desc) == 1:
                            # Single command found
                            extracted_command = commands_with_desc[0].get("command", "")
                            # Show command BEFORE asking for confirmation
                            print_command(extracted_command)
                            if click.confirm(
                                click.style("Execute this command? [y/N]", fg="yellow", bold=True),
                                default=False
                            ):
                                # User confirmed - execute the command directly
                                click.echo()  # New line
                                executor = CommandExecutor()
                                
                                # Check for sudo
                                if not allow_sudo and executor.has_sudo(extracted_command):
                                    print_error("Sudo commands are not allowed. Use --sudo flag to enable.")
                                    continue
                                
                                # Execute command (already shown above)
                                try:
                                    returncode, stdout, stderr = executor.execute_command(
                                        extracted_command,
                                        confirm=not yes,  # Use yes flag to skip confirmation
                                        show_output=False,  # We'll display it ourselves
                                        allow_sudo=allow_sudo,
                                        timeout=timeout
                                    )
                                    
                                    # Display output
                                    if stdout:
                                        click.echo(click.style("📤 Command Output (stdout):", fg="blue", bold=True))
                                        click.echo(stdout)
                                    else:
                                        click.echo(click.style("📤 Command Output (stdout): (empty)", fg="blue", dim=True))
                                    
                                    if stderr:
                                        click.echo()  # Blank line before stderr
                                        click.echo(click.style("⚠️  Command Error Output (stderr):", fg="red", bold=True))
                                        click.echo(click.style(stderr, fg="red"), err=True)
                                    
                                    click.echo()  # Blank line after output
                                    click.echo(click.style(f"Return code: {returncode}", fg="cyan"))
                                    
                                    if returncode == 0:
                                        print_success("✓ Command executed successfully")
                                    else:
                                        print_error(f"Command exited with code {returncode}")
                                    
                                    # Add command execution to conversation history and continue
                                    command_result = f"Command executed: {extracted_command}\nReturn code: {returncode}\n"
                                    if stdout:
                                        command_result += f"Stdout:\n{stdout}\n"
                                    if stderr:
                                        command_result += f"Stderr:\n{stderr}\n"
                                    
                                    conversation_history.append({"role": "user", "content": f"Execute: {extracted_command}"})
                                    conversation_history.append({"role": "assistant", "content": command_result})
                                    
                                    # Continue conversation to answer original question
                                    click.echo()  # New line
                                    click.echo(click.style("Analyzing results...", fg="cyan", dim=True))
                                    
                                    # Generate follow-up response
                                    follow_up_response = ""
                                    for chunk in client.generate_chat(conversation_history):
                                        follow_up_response += chunk
                                        print_response(chunk)
                                    
                                    if follow_up_response:
                                        conversation_history.append({"role": "assistant", "content": follow_up_response})
                                        click.echo()  # New line after response
                                        
                                except ValueError as e:
                                    print_error(str(e))
                                except TimeoutError as e:
                                    print_error(str(e))
                                except RuntimeError as e:
                                    print_error(str(e))
                            else:
                                print_info("Command execution skipped.")
                    else:
                        # Fallback to old method for code blocks
                        all_commands = executor.extract_all_commands(full_response)
                        if all_commands:
                            click.echo()  # New line
                            
                            if len(all_commands) > 1:
                                # Multiple commands found - let user choose
                                click.echo(click.style("Multiple commands found:", fg="cyan", bold=True))
                                for i, cmd in enumerate(all_commands, 1):
                                    # Truncate long commands for display
                                    display_cmd = cmd[:80] + "..." if len(cmd) > 80 else cmd
                                    click.echo(f"  {i}. {display_cmd}")
                            
                            click.echo()
                            choice = click.prompt(
                                click.style("Select command to execute (1-{}, or N to skip): ".format(len(all_commands)), fg="yellow", bold=True),
                                type=click.Choice([str(i) for i in range(1, len(all_commands) + 1)] + ['N', 'n'], case_sensitive=False),
                                default='N'
                            )
                            
                            if choice.upper() == 'N':
                                print_info("Command execution skipped.")
                            else:
                                selected_index = int(choice) - 1
                                selected_command = all_commands[selected_index]
                                click.echo()  # New line
                                process_query_with_execution(
                                    client, 
                                    f"Execute: {selected_command}",
                                    auto_confirm=yes,
                                    max_iterations=max_iterations,
                                    allow_sudo=allow_sudo,
                                    timeout=timeout
                                )
                        elif len(all_commands) == 1:
                            # Single command found
                            extracted_command = all_commands[0]
                            # Show command BEFORE asking for confirmation
                            print_command(extracted_command)
                            if click.confirm(
                                click.style("Execute this command? [y/N]", fg="yellow", bold=True),
                                default=False
                            ):
                                # User confirmed - execute the command
                                click.echo()  # New line
                                process_query_with_execution(
                                    client, 
                                    f"Execute: {extracted_command}",
                                    auto_confirm=yes,
                                    max_iterations=max_iterations,
                                    allow_sudo=allow_sudo,
                                    timeout=timeout
                                )
                            else:
                                print_info("Command execution skipped.")
            except OllamaConnectionError as e:
                print_error(str(e))
                click.echo("Please check your Ollama connection and configuration.")
                # Remove the user message from history if request failed
                if conversation_history and conversation_history[-1]["role"] == "user":
                    conversation_history.pop()
            except OllamaAPIError as e:
                print_error(str(e))
                # Remove the user message from history if request failed
                if conversation_history and conversation_history[-1]["role"] == "user":
                    conversation_history.pop()

        except KeyboardInterrupt:
            click.echo("\n\nGoodbye!")
            # Save history before exiting
            if READLINE_AVAILABLE and history_file:
                try:
                    readline.write_history_file(str(history_file))
                except Exception:
                    pass  # Ignore errors saving history
            break
        except EOFError:
            click.echo("\nGoodbye!")
            # Save history before exiting
            if READLINE_AVAILABLE and history_file:
                try:
                    readline.write_history_file(str(history_file))
                except Exception:
                    pass  # Ignore errors saving history
            break


@click.command()
@click.argument("query", required=False)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Start interactive mode",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=click.Path),
    help="Path to configuration file",
)
@click.option(
    "--model",
    "-m",
    help="Override model from config",
)
@click.option(
    "--temperature",
    "-t",
    type=float,
    help="Override temperature from config (0.0-2.0)",
)
@click.option(
    "--endpoint",
    "-e",
    help="Override Ollama endpoint from config",
)
@click.option(
    "--execute",
    "-x",
    is_flag=True,
    help="Enable command execution mode (AI can run commands for you)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Auto-confirm command execution (use with caution)",
)
@click.option(
    "--sudo",
    "--allow-sudo",
    is_flag=True,
    help="Allow sudo commands (disabled by default for security)",
)
@click.option(
    "--max-iterations",
    type=int,
    default=5,
    help="Maximum number of command execution iterations (default: 5, use -1 for infinite)",
)
@click.option(
    "--timeout",
    type=int,
    default=30,
    help="Command execution timeout in seconds (default: 30, use -1 for infinite)",
)
@click.option(
    "--platform-info",
    is_flag=True,
    help="Show detected platform information and exit",
)
@click.option(
    "--debug",
    "-d",
    is_flag=True,
    help="Enable debug mode to see all prompts sent to Ollama and application logic flow",
)
@click.version_option(version=__version__)
def main(
    query: Optional[str],
    interactive: bool,
    config: Optional[click.Path],
    model: Optional[str],
    temperature: Optional[float],
    endpoint: Optional[click.Path],
    execute: bool,
    yes: bool,
    sudo: bool,
    max_iterations: int,
    timeout: int,
    platform_info: bool,
    debug: bool,
) -> None:
    """
    Command Line Assistant - Ollama-powered CLI assistant.

    Ask a question directly or use interactive mode.
    """
    # Enable debug mode if requested
    if debug:
        set_debug_mode(True)
        logger = get_logger(__name__)
        logger.debug("=" * 80)
        logger.debug("DEBUG MODE ENABLED")
        logger.debug("=" * 80)
        logger.debug("All prompts sent to Ollama will be logged with context")
        logger.debug("Application logic flow will be displayed")
        logger.debug("=" * 80)
    
    # Handle platform info request
    if platform_info:
        detector = PlatformDetector()
        info = detector.get_platform_info()
        click.echo(click.style("Platform Detection Information", fg="cyan", bold=True))
        click.echo()
        click.echo(f"Platform: {click.style(info['platform'], fg='green', bold=True)}")
        click.echo(f"Distribution: {click.style(info['distribution'], fg='green')}")
        click.echo(f"Version: {click.style(info['version'], fg='green')}")
        click.echo()
        click.echo(click.style("Detection Reason:", fg="yellow", bold=True))
        click.echo(f"  {info['detection_reason']}")
        click.echo()
        click.echo(click.style("Platform-Specific Commands:", fg="yellow", bold=True))
        for cmd_type, cmd_value in info['commands'].items():
            if cmd_type != 'alternatives':  # Skip alternatives for cleaner output
                click.echo(f"  {cmd_type}: {click.style(cmd_value, fg='cyan')}")
        click.echo()
        click.echo(f"Primary Package Manager: {click.style(info['package_manager'], fg='cyan', bold=True)}")
        return

    try:
        # Load configuration
        try:
            cfg = get_config(config_path=config)
        except ConfigurationError as e:
            print_error(str(e))
            sys.exit(1)

        # Override config with CLI options
        if model:
            cfg._config["ollama"]["model"] = model
        if temperature is not None:
            if not (0.0 <= temperature <= 2.0):
                print_error("Temperature must be between 0.0 and 2.0")
                sys.exit(1)
            cfg._config["ollama"]["temperature"] = temperature
        if endpoint:
            cfg._config["ollama"]["endpoint"] = endpoint

        # Create client
        client = OllamaClient(cfg)

        # Validate max_iterations
        if max_iterations < -1 or max_iterations == 0:
            print_error("max-iterations must be -1 (infinite) or a positive integer")
            sys.exit(1)
        
        # Validate timeout
        if timeout < -1 or timeout == 0:
            print_error("timeout must be -1 (infinite) or a positive integer")
            sys.exit(1)
        
        # Determine mode
        if interactive or (query is None and sys.stdin.isatty()):
            interactive_mode(client, execute=execute, yes=yes, allow_sudo=sudo, max_iterations=max_iterations, timeout=timeout)
        elif query:
            # Single query mode - sanitize input
            sanitizer = InputSanitizer()
            try:
                query = sanitizer.sanitize_query(query)
            except ValueError as e:
                print_error(f"Invalid input: {e}")
                sys.exit(1)
            
            try:
                if execute:
                    if is_debug_mode():
                        logger = get_logger(__name__)
                        logger.debug("=" * 80)
                        logger.debug("SINGLE QUERY MODE: Execute mode")
                        logger.debug("=" * 80)
                        logger.debug(f"Query: {query}")
                        logger.debug("=" * 80)
                    process_query_with_execution(client, query, auto_confirm=yes, allow_sudo=sudo, max_iterations=max_iterations, timeout=timeout)
                else:
                    if is_debug_mode():
                        logger = get_logger(__name__)
                        logger.debug("=" * 80)
                        logger.debug("SINGLE QUERY MODE: Non-execute mode")
                        logger.debug("=" * 80)
                        logger.debug(f"Query: {query}")
                        logger.debug("Reason: Simple query, sending directly to Ollama")
                        logger.debug("=" * 80)
                    for chunk in client.generate(query):
                        print_response(chunk)
                    click.echo()  # New line after response
            except OllamaConnectionError as e:
                print_error(str(e))
                click.echo("Please check your Ollama connection and configuration.")
                sys.exit(1)
            except OllamaAPIError as e:
                print_error(str(e))
                sys.exit(1)
        else:
            # Read from stdin - sanitize input
            sanitizer = InputSanitizer()
            raw_prompt = sys.stdin.read().strip()
            if not raw_prompt:
                print_error("No input provided")
                sys.exit(1)

            try:
                prompt = sanitizer.sanitize_query(raw_prompt)
            except ValueError as e:
                print_error(f"Invalid input: {e}")
                sys.exit(1)

            try:
                if execute:
                    if is_debug_mode():
                        logger = get_logger(__name__)
                        logger.debug("=" * 80)
                        logger.debug("STDIN MODE: Execute mode")
                        logger.debug("=" * 80)
                        logger.debug(f"Query: {prompt}")
                        logger.debug("=" * 80)
                    process_query_with_execution(client, prompt, auto_confirm=yes, allow_sudo=sudo, max_iterations=max_iterations, timeout=timeout)
                else:
                    if is_debug_mode():
                        logger = get_logger(__name__)
                        logger.debug("=" * 80)
                        logger.debug("STDIN MODE: Non-execute mode")
                        logger.debug("=" * 80)
                        logger.debug(f"Query: {prompt}")
                        logger.debug("Reason: Simple query from stdin, sending directly to Ollama")
                        logger.debug("=" * 80)
                    for chunk in client.generate(prompt):
                        print_response(chunk)
                    click.echo()  # New line after response
            except OllamaConnectionError as e:
                print_error(str(e))
                click.echo("Please check your Ollama connection and configuration.")
                sys.exit(1)
            except OllamaAPIError as e:
                print_error(str(e))
                sys.exit(1)

    except CommandLineAssistantError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


def process_query_with_execution(
    client: OllamaClient,
    query: str,
    auto_confirm: bool = False,
    max_iterations: int = 5,
    allow_sudo: bool = False,
    timeout: int = 30,
) -> None:
    """
    Process a query with command execution capability and output analysis.

    Args:
        client: Ollama client instance.
        query: User query.
        auto_confirm: Whether to auto-confirm command execution.
        max_iterations: Maximum number of command execution iterations.
        allow_sudo: Whether to allow sudo commands (default: False).
    """
    import os
    logger = get_logger(__name__)
    logger.info(f"Processing query with execution: {query[:50]}...")
    
    if is_debug_mode():
        logger.debug("=" * 80)
        logger.debug("PROCESS QUERY WITH EXECUTION")
        logger.debug("=" * 80)
        logger.debug(f"Query: {query}")
        logger.debug(f"Auto-confirm: {auto_confirm}")
        logger.debug(f"Max iterations: {max_iterations}")
        logger.debug(f"Allow sudo: {allow_sudo}")
        logger.debug(f"Timeout: {timeout}")
        logger.debug("=" * 80)

    # Get current working directory for context
    cwd = Path(os.getcwd())
    
    # Pre-step: Evaluate query to determine if local context is needed
    # Use Ollama for strategy selection if client is available and not in test mode
    # Disable Ollama in tests to avoid needing complex mocks
    use_ollama = os.getenv("CLA_USE_OLLAMA_STRATEGY", "true").lower() == "true"
    if is_debug_mode():
        logger.debug(f"Evaluating query to determine if local context is needed...")
        logger.debug(f"Using Ollama for strategy selection: {use_ollama}")
    query_evaluator = QueryEvaluator(use_ollama=use_ollama, ollama_client=client)
    query_context = query_evaluator.evaluate_query(query, cwd)
    if is_debug_mode():
        logger.debug(f"Query evaluation result:")
        logger.debug(f"  - Needs local context: {query_context.needs_local_context}")
        logger.debug(f"  - Target path: {query_context.target_path}")
        logger.debug(f"  - Query type: {query_context.query_type}")
    
    # Build optimized system prompt with self-learning
    if is_debug_mode():
        logger.debug("Building system prompt with PromptBuilder...")
    prompt_builder = PromptBuilder()
    
    # Set environment context for this session (always set, not just when local context is needed)
    shell = os.environ.get("SHELL", "bash")
    if shell:
        shell_name = shell.split("/")[-1]
        prompt_builder.record_environment_context("shell", shell_name)  # Extract shell name
        if is_debug_mode():
            logger.debug(f"Recorded environment context: shell={shell_name}")
    
    # Record current working directory in environment context
    prompt_builder.record_environment_context("working_directory", str(cwd))
    if is_debug_mode():
        logger.debug(f"Recorded environment context: working_directory={cwd}")
    
    # Collect local context if needed
    context_attachment = ""
    context_collector = None
    if query_context.needs_local_context:
        logger.info(f"Query needs local context. Target path: {query_context.target_path}")
        if is_debug_mode():
            logger.debug("Collecting local context...")
        context_collector = ContextCollector()
        target_path = query_context.target_path or cwd
        if is_debug_mode():
            logger.debug(f"Target path for context collection: {target_path}")
        
        # Get directory tree
        tree = context_collector.get_directory_tree(target_path, max_depth=4)
        
        # Collect context files
        context_files = context_collector.collect_context_files(target_path)
        
        # Detect and record project type from files
        if "package.json" in context_files:
            prompt_builder.record_environment_context("project_type", "nodejs")
        elif "pyproject.toml" in context_files or "setup.py" in context_files or "requirements.txt" in context_files:
            prompt_builder.record_environment_context("project_type", "python")
        elif "Cargo.toml" in context_files:
            prompt_builder.record_environment_context("project_type", "rust")
        elif "pom.xml" in context_files or "build.gradle" in context_files:
            prompt_builder.record_environment_context("project_type", "java")
        elif "go.mod" in context_files:
            prompt_builder.record_environment_context("project_type", "go")
        
        # Format as attachment
        if tree or context_files:
            context_attachment = context_collector.format_context_attachment(tree, context_files)
            logger.debug(f"Collected context: tree={bool(tree)}, files={len(context_files)}")
    
    # Build system prompt (includes environment context) - rebuild to include any newly set context
    system_prompt = prompt_builder.build_system_prompt(allow_sudo=allow_sudo)
    
    # Add current directory context to system prompt
    system_prompt += f"\n\n**CURRENT WORKING DIRECTORY:** {cwd}\nWhen investigating projects or files, start by checking the current directory: `ls -la`, `cat README.md`, `head package.json`, etc."

    executor = CommandExecutor()
    current_query = query
    iteration = 0
    last_output = ""
    last_stderr = ""
    last_returncode = 0
    last_command = None  # Track last executed command for learning
    pending_error_context = None  # Track errors for learning after successful fix
    need_to_read_files = False  # Flag to track if we need to read project files
    context_added = False  # Track if context attachment has been added
    
    # Handle infinite iterations (-1)
    infinite = (max_iterations == -1)
    
    while infinite or iteration < max_iterations:
        iteration += 1
        
        # Build context for AI (include previous command output if available)
        if iteration > 1:
            # This is a follow-up iteration - include previous command results
            # Also include relevant learned patterns for similar queries
            relevant_patterns = prompt_builder.get_relevant_patterns(current_query, limit=2)
            patterns_context = ""
            if relevant_patterns:
                patterns_context = "\n\n**Similar successful patterns from past experience:**\n"
                for pattern in relevant_patterns:
                    patterns_context += f"- Query: \"{pattern['query']}\" used: `{pattern['command']}`\n"
            
            context_query = f"""{current_query}{patterns_context}

Previous command output:
Return code: {last_returncode}
Stdout:
{last_output}
Stderr:
{last_stderr}

Based on this output, what should we do next? If the task is complete, say so. If there are errors, analyze them and suggest fixes. If more commands are needed, provide them."""
        else:
            # First iteration - add context attachment if available
            if context_attachment and not context_added:
                context_query = f"{current_query}\n\n{context_attachment}"
                context_added = True
            else:
                context_query = current_query
        
        # Try structured outputs first (more reliable), fallback to legacy format
        use_structured = False
        structured_response = None
        full_response = ""
        command = None
        thinking = ""
        task_complete = False
        command_options = []  # Initialize here so it's available in exception handler

        try:
            # Rebuild system prompt to ensure environment context is up-to-date
            # This ensures any context learned during execution is included
            if is_debug_mode():
                logger.debug(f"Iteration {iteration}: Building system prompt...")
            system_prompt = prompt_builder.build_system_prompt(allow_sudo=allow_sudo)
            # Add current directory context to system prompt
            system_prompt += f"\n\n**CURRENT WORKING DIRECTORY:** {cwd}\nWhen investigating projects or files, start by checking the current directory: `ls -la`, `cat README.md`, `head package.json`, etc."
            
            if is_debug_mode():
                logger.debug(f"Iteration {iteration}: Sending request to Ollama with structured output format...")
                logger.debug(f"Context query: {context_query[:200]}...")
            # Use structured outputs for better reliability
            schema = get_command_response_schema()
            structured_response = client.generate_with_system_prompt_structured(
                user_prompt=context_query,
                system_prompt=system_prompt,
                format_schema=schema,
            )
            if is_debug_mode():
                logger.debug(f"Iteration {iteration}: Received structured response from Ollama")
                logger.debug(f"  - Has thinking: {bool(structured_response.get('thinking'))}")
                logger.debug(f"  - Commands count: {len(structured_response.get('commands', []))}")
                logger.debug(f"  - Task complete: {structured_response.get('task_complete', False)}")
            
            use_structured = True
            thinking = structured_response.get("thinking", "")
            commands_array = structured_response.get("commands", [])
            task_complete_raw = structured_response.get("task_complete", False)
            
            # Backward compatibility: check for old "command" field
            command_raw = structured_response.get("command")
            if command_raw and not commands_array:
                # Old format - convert to new format
                commands_array = [{"description": "Execute command", "command": command_raw}]
            
            # Override task_complete if we need to read project files
            if need_to_read_files:
                task_complete = False
                logger.info("Overriding task_complete=False because we need to read project files")
            else:
                task_complete = task_complete_raw
            
            # Process commands array
            command = None
            # command_options already initialized above
            
            if commands_array:
                sanitizer = InputSanitizer()
                for cmd_obj in commands_array:
                    if not isinstance(cmd_obj, dict):
                        continue
                    
                    cmd_text = cmd_obj.get("command", "").strip()
                    cmd_description = cmd_obj.get("description", "").strip()
                    
                    if not cmd_text:
                        continue
                    
                    # Sanitize command text
                    sanitized_cmd = sanitizer.sanitize_ai_response(cmd_text)
                    
                    # Remove code block markers if present
                    sanitized_cmd = re.sub(r'^```(?:bash|sh)?\s*\n?', '', sanitized_cmd)
                    sanitized_cmd = re.sub(r'\n?```\s*$', '', sanitized_cmd)
                    sanitized_cmd = sanitized_cmd.strip()
                    
                    # Validate that this looks like an actual command
                    conversational_patterns = [
                        r'^(Asking|Please|I will|Let me|You should|We need|This is|That is)',
                        r'^(No code block|No command|N/A|None|null)$',
                        r'^\(.*\)$',  # Text in parentheses like "(No code block)"
                    ]
                    if any(re.match(pattern, sanitized_cmd, re.IGNORECASE) for pattern in conversational_patterns):
                        logger.warning(f"Rejected conversational text as command: {sanitized_cmd}")
                        continue
                    
                    # Sanitize the command
                    try:
                        sanitized_cmd = sanitizer.sanitize_command(sanitized_cmd)
                        command_options.append({
                            "description": cmd_description or "Execute command",
                            "command": sanitized_cmd
                        })
                    except ValueError as e:
                        logger.warning(f"Command sanitization failed: {e}")
                        continue
                
                # If only one command, use it directly
                if len(command_options) == 1:
                    command = command_options[0]["command"]
                elif len(command_options) > 1:
                    # Multiple commands - will be handled in user selection below
                    pass
            
            # Check if AI is asking a question (interactive mode) - do this BEFORE displaying thinking
            # to avoid displaying thinking twice
            is_question = False
            has_commands = command or (command_options and len(command_options) > 0)
            if not has_commands and not task_complete and thinking:
                # Detect question words or question marks
                question_words = ["what", "which", "do you", "should", "would", "could", "can you", "please", "?"]
                is_question = any(word in thinking.lower() for word in question_words) or "?" in thinking
            
            # Display thinking - but skip if it's a question (will be displayed below with question label)
            if thinking and not is_question:
                print_thinking(thinking)
            elif not thinking and not command:
                # If no thinking and no command, something might be wrong
                logger.warning("Structured response has no thinking and no command")
            
            # Log the full structured response for debugging
            logger.debug(f"Structured response: thinking={bool(thinking)}, command={bool(command)}, complete={task_complete}, full_response={structured_response}")
            
            # If we have thinking but no command and task is not complete, 
            # the AI might be waiting or the response might be incomplete
            if thinking and not command and not task_complete and not is_question:
                logger.debug("AI provided thinking but no command - may need to investigate or provide information")
            
            # Display question if detected
            if is_question:
                # AI is asking for user input - use thinking output for the question
                click.echo()  # New line
                click.echo(click.style("🤔 AI Question:", fg="cyan", bold=True))
                click.echo(thinking)  # Use the thinking output
                click.echo()  # New line
                
                # Get user input
                try:
                    user_input = click.prompt(
                        click.style("Your response", fg="yellow"),
                        default="",
                        show_default=False
                    ).strip()
                    
                    if user_input.lower() in ("skip", "continue", ""):
                        # User wants to skip or continue without input
                        logger.info("User skipped question, continuing")
                    else:
                        # Add user response to query for next iteration
                        current_query = f"{current_query}\n\nUser response: {user_input}"
                        logger.info(f"User provided response: {user_input[:50]}...")
                        continue  # Continue to next iteration
                except (KeyboardInterrupt, EOFError):
                    click.echo("\nCancelled.")
                    return
            
        except (OllamaAPIError, OllamaConnectionError) as e:
            # Fallback to legacy format if structured outputs fail
            logger.warning(f"Structured outputs failed, using legacy format: {e}")
            if is_debug_mode():
                logger.debug(f"Iteration {iteration}: Falling back to legacy format due to error: {e}")
            use_structured = False
            
            # Rebuild system prompt to ensure environment context is up-to-date
            system_prompt = prompt_builder.build_system_prompt(allow_sudo=allow_sudo)
            # Add current directory context to system prompt
            system_prompt += f"\n\n**CURRENT WORKING DIRECTORY:** {cwd}\nWhen investigating projects or files, start by checking the current directory: `ls -la`, `cat README.md`, `head package.json`, etc."
            
            if is_debug_mode():
                logger.debug(f"Iteration {iteration}: Sending request to Ollama with legacy format...")
            # Generate response with system prompt (legacy)
            click.echo()  # New line before response
            
            # Stream the thinking process
            for chunk in client.generate_with_system_prompt(context_query, system_prompt):
                print_response(chunk)
                full_response += chunk
            
            click.echo()  # New line after response
            
            # Sanitize AI response before parsing
            sanitizer = InputSanitizer()
            sanitized_response = sanitizer.sanitize_ai_response(full_response)
            
            # Extract command from response
            command = executor.extract_command(sanitized_response)
            
            # Sanitize extracted command
            if command:
                try:
                    command = sanitizer.sanitize_command(command)
                except ValueError as e:
                    logger.warning(f"Command sanitization failed: {e}")
                    command = None
            
            # Extract thinking/conversational text (everything except code blocks)
            thinking = executor.format_thinking(sanitized_response)
            # Initialize command_options for legacy path (will be empty, handled below)
            command_options = []
        
        # Handle multiple command options
        if command_options and len(command_options) > 1:
            # Multiple commands - let user choose (unless auto_confirm is enabled)
            if auto_confirm:
                # Auto-select first command when --yes is used
                command = command_options[0]["command"]
                if is_debug_mode():
                    logger.debug(f"Auto-selected first command from {len(command_options)} options (auto_confirm=True)")
            else:
                # Multiple commands - let user choose
                click.echo()  # New line
                click.echo(click.style("Multiple command options:", fg="cyan", bold=True))
                for i, cmd_opt in enumerate(command_options, 1):
                    display_cmd = cmd_opt["command"][:60] + "..." if len(cmd_opt["command"]) > 60 else cmd_opt["command"]
                    click.echo(f"  {i}. {click.style(cmd_opt['description'], fg='yellow')}: {display_cmd}")
                
                click.echo()
                try:
                    choice = click.prompt(
                        click.style("Select command to execute (1-{}, or N to skip): ".format(len(command_options)), fg="yellow", bold=True),
                        type=click.Choice([str(i) for i in range(1, len(command_options) + 1)] + ['N', 'n'], case_sensitive=False),
                        default='N'
                    )
                    
                    if choice.upper() == 'N':
                        print_info("Command execution skipped.")
                        command = None
                    else:
                        selected_index = int(choice) - 1
                        command = command_options[selected_index]["command"]
                        click.echo()  # New line
                except (KeyboardInterrupt, EOFError):
                    click.echo("\nCancelled.")
                    return
        
        if command:
            # Command found - show command and execute
            # Note: thinking already displayed above for structured outputs
            if not use_structured and thinking:
                print_thinking(thinking)
            
            # Show command BEFORE asking for confirmation (so user knows what they're confirming)
            print_command(command)
            
            # Check if dangerous
            if executor.is_dangerous(command):
                print_error(f"Command is too dangerous to execute: {command}")
                return
            
            # Check if confirmation needed
            if not auto_confirm and executor.requires_confirmation(command):
                if not click.confirm(
                    click.style(
                        f"⚠️  This command may modify your system. Execute it?",
                        fg="yellow",
                    )
                ):
                    print_info("Command execution cancelled.")
                    return
            
            # Handle sudo if disabled (default behavior)
            original_command = command
            if not allow_sudo and executor.has_sudo(command):
                command = executor.strip_sudo(command)
                print_info(f"⚠️  Sudo removed from command (sudo disabled by default): {original_command} → {command}")
                print_info("💡 To enable sudo, run the command again with the --sudo or --allow-sudo flag")
                print_info("   Example: cla --execute --sudo \"your command here\"")
            
            # Execute command
            if is_debug_mode():
                logger.debug("=" * 80)
                logger.debug("COMMAND EXECUTION")
                logger.debug("=" * 80)
                logger.debug(f"Command: {command}")
                logger.debug(f"Allow sudo: {allow_sudo}")
                logger.debug(f"Timeout: {timeout}")
                logger.debug("=" * 80)
            try:
                returncode, stdout, stderr = executor.execute_command(
                    command, confirm=False, show_output=True, allow_sudo=allow_sudo, timeout=timeout
                )
                if is_debug_mode():
                    logger.debug(f"Command execution completed:")
                    logger.debug(f"  - Return code: {returncode}")
                    logger.debug(f"  - Stdout length: {len(stdout)} characters")
                    logger.debug(f"  - Stderr length: {len(stderr)} characters")
                    if stdout:
                        logger.debug(f"  - Stdout preview: {stdout[:200]}...")
                    if stderr:
                        logger.debug(f"  - Stderr preview: {stderr[:200]}...")
                    logger.debug("=" * 80)
                
                # Store output and command for next iteration
                last_output = stdout
                last_stderr = stderr
                last_returncode = returncode
                last_command = command
                
                # Show output with clear labels
                click.echo()  # Blank line before output
                if stdout:
                    click.echo(click.style("📤 Command Output (stdout):", fg="blue", bold=True))
                    click.echo(stdout)
                else:
                    click.echo(click.style("📤 Command Output (stdout): (empty)", fg="blue", dim=True))
                
                if stderr:
                    click.echo()  # Blank line before stderr
                    click.echo(click.style("⚠️  Command Error Output (stderr):", fg="red", bold=True))
                    click.echo(click.style(stderr, fg="red"), err=True)
                
                click.echo()  # Blank line after output
                click.echo(click.style(f"Return code: {returncode}", fg="cyan"))
                
                if returncode == 0:
                    print_success("✓ Command executed successfully")
                    # Record successful pattern for learning
                    original_query = query if iteration == 1 else current_query.split('\n')[0]  # Get first line for context
                    prompt_builder.record_success(original_query, command, stdout)
                    
                    # If this command fixed a previous error, record the error-solution pair
                    if pending_error_context:
                        # Extract the solution command from the thinking or full response
                        solution_command = command
                        prompt_builder.record_error_solution(
                            pending_error_context["error"],
                            solution_command
                        )
                        pending_error_context = None
                    
                    # Check if output contains project files that should be read
                    # Look for project files in the output (case-insensitive)
                    project_files = ['README.md', 'README.txt', 'README', 'package.json', 'pyproject.toml', 'Cargo.toml', 'pom.xml', 'build.gradle', 'setup.py']
                    stdout_lower = stdout.lower()
                    found_files = [f for f in project_files if f.lower() in stdout_lower or f in stdout]
                    
                    # Check if this is an investigative query and we found project files
                    investigation_queries = ["what is", "what's", "explain", "describe", "tell me about"]
                    is_investigative = any(keyword in query.lower() for keyword in investigation_queries)
                    
                    if found_files and is_investigative and iteration < max_iterations:
                        # Found project files in an investigative query - prompt to read them
                        need_to_read_files = True  # Set flag to override task_complete
                        files_to_read = found_files[:2]  # Limit to first 2 files
                        read_commands = []
                        for file in files_to_read:
                            if file.endswith('.md') or file.endswith('.txt'):
                                read_commands.append(f"cat {file} 2>/dev/null || head -50 {file} 2>/dev/null")
                            elif file in ['package.json', 'pyproject.toml', 'Cargo.toml', 'pom.xml']:
                                read_commands.append(f"head -30 {file} 2>/dev/null || cat {file} 2>/dev/null")
                            else:
                                read_commands.append(f"cat {file} 2>/dev/null || head -50 {file} 2>/dev/null")
                        
                        current_query = f"""I found these project files in the directory listing: {', '.join(found_files)}

Please read them to understand what this project is. Use commands like:
{chr(10).join(f'- `{cmd}`' for cmd in read_commands)}

Read the files and then provide a summary of what this project is."""
                        logger.info(f"Found project files {found_files} - will continue to read them")
                    else:
                        current_query = "Analyze the command output above and determine if the task is complete or if more actions are needed."
                        need_to_read_files = False  # Reset flag
                else:
                    print_error(f"Command exited with code {returncode}")
                    # Check for known error solutions
                    error_solution = None
                    if stderr:
                        error_solution = prompt_builder.get_error_solution(stderr)
                    
                    # Store error context for learning if a fix is provided later
                    pending_error_context = {
                        "error": stderr[:200] if stderr else stdout[:200],
                        "failed_command": command,
                    }
                    
                    # Build context for next iteration
                    if error_solution:
                        current_query = f"Previous command failed. Known solution from past experience: {error_solution}\n\nCommand output:\nReturn code: {returncode}\nStdout:\n{stdout}\nStderr:\n{stderr}\n\nApply the solution or provide an alternative approach."
                    else:
                        current_query = f"Previous command failed. Analyze the error and provide a solution.\n\nCommand output:\nReturn code: {returncode}\nStdout:\n{stdout}\nStderr:\n{stderr}"
                    
            except ValueError as e:
                print_error(str(e))
                return
            except TimeoutError as e:
                print_error(str(e))
                return
            except RuntimeError as e:
                print_error(str(e))
                return
            except Exception as e:
                print_error(f"Unexpected error executing command: {e}")
                return
        else:
            # No command found - AI is either:
            # 1. Asking for clarification (first iteration)
            # 2. Indicating task is complete (subsequent iterations)
            # 3. Warning about safety
            # 4. Providing information without needing a command
            # 5. Thinking indicates investigation but forgot to provide command
            
            # Check if this is an informational/investigative query that needs commands
            investigation_queries = ["what is", "what's", "explain", "describe", "tell me about", "show me", "analyze"]
            is_investigative_query = any(keyword in query.lower() for keyword in investigation_queries)
            
            # Check if thinking suggests the AI wants to investigate but didn't provide a command
            investigation_keywords = ["will look", "will check", "will examine", "will investigate", "need to check", "need to look", "should check", "should look", "examining", "analyzing", "checking", "looking", "cannot determine", "cannot find", "no specific", "appears that"]
            thinking_suggests_investigation = thinking and any(keyword in thinking.lower() for keyword in investigation_keywords)
            
            # If it's an investigative query and no command was provided, prompt for investigation commands
            if (is_investigative_query or thinking_suggests_investigation) and iteration == 1 and not command:
                # AI wants to investigate but didn't provide command - prompt it to do so
                logger.info("Investigative query detected but no command provided - prompting for investigation commands")
                current_query = f"""{query}

You need to investigate to answer this question. Please provide commands to examine the current directory and project files.
Current directory: {cwd}

Use commands like:
- `ls -la` to see directory contents
- `cat README.md` or `head README.md` to read the README
- `head package.json` or `head pyproject.toml` or `head Cargo.toml` for project metadata
- `find . -maxdepth 2 -name "*.md" -o -name "*.txt"` to find documentation files

Provide the command(s) to investigate this project."""
                continue  # Continue to next iteration instead of breaking
            
            # Ensure user sees the response even if no command is provided
            if use_structured:
                # Thinking already displayed above if it exists
                # If no thinking was shown, the AI might have provided an empty response
                if not thinking:
                    logger.warning("Structured response has no thinking and no command")
                    print_info("No command needed. If you expected a response, the AI may need more context.")
            else:
                # Legacy format - full response was already streamed above
                # But if thinking wasn't extracted, ensure we show something
                if not thinking and not full_response.strip():
                    print_info("No response received from AI.")
            
            # Check if structured response indicated task completion
            if use_structured and task_complete:
                if last_returncode == 0 and last_command:
                    original_query = query if iteration == 1 else current_query.split('\n')[0]
                    prompt_builder.record_success(original_query, last_command, last_output)
                if thinking:
                    # Thinking already shown, just indicate completion
                    print_info("\nTask completed.")
                else:
                    print_info("Task completed.")
                break
            
            if iteration > 1:
                # This means task is likely complete
                # Record successful completion if last command succeeded
                if last_returncode == 0 and last_command:
                    original_query = query if iteration == 2 else current_query.split('\n')[0]
                    prompt_builder.record_success(original_query, last_command, last_output)
                print_info("Task completed or no further actions needed.")
            else:
                # First iteration with no command - AI is providing information or asking for clarification
                # If we have thinking, it was already shown. If not, something went wrong.
                if not thinking and use_structured:
                    logger.warning("First iteration: no command and no thinking in structured response")
                    print_error("No response from AI. The query may need to be more specific or there may be a connection issue.")
            break
    
    if not infinite and iteration >= max_iterations:
        print_info(f"Reached maximum iterations ({max_iterations}). Stopping.")


if __name__ == "__main__":
    main()

