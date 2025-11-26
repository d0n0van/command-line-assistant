"""CLI interface for command-line-assistant."""

import re
import sys
from typing import Optional

import click

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
from command_line_assistant.logger import get_logger
from command_line_assistant.schemas import get_command_response_schema
from command_line_assistant.sanitizer import InputSanitizer


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
    click.echo("Type 'quit', 'exit', or 'q' to exit")
    click.echo("Type 'clear' to clear conversation history")
    click.echo("=" * 50)

    sanitizer = InputSanitizer()
    # Maintain conversation history for context
    conversation_history: list[Dict[str, str]] = []
    
    while True:
        try:
            raw_prompt = input("\n> ").strip()

            if not raw_prompt:
                continue

            if raw_prompt.lower() in ("quit", "exit", "q"):
                click.echo("Goodbye!")
                break

            # Clear conversation history
            if raw_prompt.lower() == "clear":
                conversation_history = []
                click.echo(click.style("Conversation history cleared.", fg="green"))
                continue

            # Sanitize user input
            try:
                prompt = sanitizer.sanitize_query(raw_prompt)
            except ValueError as e:
                print_error(f"Invalid input: {e}")
                continue

            # Generate and stream response
            click.echo()  # New line before response
            try:
                if execute:
                    # For execute mode, we still use the existing process_query_with_execution
                    # which maintains its own context for command execution iterations
                    process_query_with_execution(client, prompt, yes, max_iterations=max_iterations, allow_sudo=allow_sudo, timeout=timeout)
                    # Add to history after execution
                    conversation_history.append({"role": "user", "content": prompt})
                    # Note: We don't add the full execution output to history to keep it manageable
                    # The execution mode maintains its own context for command iterations
                else:
                    # Add user message to history
                    conversation_history.append({"role": "user", "content": prompt})
                    
                    # Generate response with conversation history
                    full_response = ""
                    for chunk in client.generate_chat(conversation_history):
                        print_response(chunk)
                        full_response += chunk
                    
                    # Add assistant response to history
                    if full_response:
                        conversation_history.append({"role": "assistant", "content": full_response})
                    
                    click.echo()  # New line after response
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
            click.echo("\n\nInterrupted. Use 'quit' to exit.")
        except EOFError:
            click.echo("\nGoodbye!")
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
) -> None:
    """
    Command Line Assistant - Ollama-powered CLI assistant.

    Ask a question directly or use interactive mode.
    """
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
                    process_query_with_execution(client, query, yes, allow_sudo=sudo, max_iterations=max_iterations, timeout=timeout)
                else:
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
                    process_query_with_execution(client, prompt, yes, allow_sudo=sudo, max_iterations=max_iterations, timeout=timeout)
                else:
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

    # Get current working directory for context
    cwd = os.getcwd()
    
    # Build optimized system prompt with self-learning
    prompt_builder = PromptBuilder()
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
            context_query = current_query
        
        # Try structured outputs first (more reliable), fallback to legacy format
        use_structured = False
        structured_response = None
        full_response = ""
        command = None
        thinking = ""
        task_complete = False

        try:
            # Use structured outputs for better reliability
            schema = get_command_response_schema()
            structured_response = client.generate_with_system_prompt_structured(
                user_prompt=context_query,
                system_prompt=system_prompt,
                format_schema=schema,
            )
            
            use_structured = True
            thinking = structured_response.get("thinking", "")
            command_raw = structured_response.get("command")
            task_complete_raw = structured_response.get("task_complete", False)
            
            # Override task_complete if we need to read project files
            if need_to_read_files:
                task_complete = False
                logger.info("Overriding task_complete=False because we need to read project files")
            else:
                task_complete = task_complete_raw
            
            # Extract command from structured response
            if command_raw:
                # Sanitize AI response before extracting command
                sanitizer = InputSanitizer()
                sanitized_response = sanitizer.sanitize_ai_response(command_raw)
                
                # Command might be in code block format or plain text
                command = executor.extract_command(sanitized_response)
                if not command:
                    # If extraction failed, try using the raw command (strip code block markers)
                    command = sanitized_response.strip()
                    # Remove ```bash and ``` markers if present
                    command = re.sub(r'^```(?:bash|sh)?\s*\n?', '', command)
                    command = re.sub(r'\n?```\s*$', '', command)
                    command = command.strip()
                
                # Validate that this looks like an actual command, not conversational text
                # Reject if it looks like conversational text (starts with capital letter, contains common phrases)
                conversational_patterns = [
                    r'^(Asking|Please|I will|Let me|You should|We need|This is|That is)',
                    r'^(No code block|No command|N/A|None|null)$',
                    r'^\(.*\)$',  # Text in parentheses like "(No code block)"
                ]
                if command and any(re.match(pattern, command, re.IGNORECASE) for pattern in conversational_patterns):
                    logger.warning(f"Rejected conversational text as command: {command}")
                    command = None
                
                # Sanitize the extracted command
                if command:
                    try:
                        command = sanitizer.sanitize_command(command)
                    except ValueError as e:
                        logger.warning(f"Command sanitization failed: {e}")
                        command = None
            
            # Display thinking
            if thinking:
                print_thinking(thinking)
            elif not command:
                # If no thinking and no command, something might be wrong
                logger.warning("Structured response has no thinking and no command")
            
            # Log the full structured response for debugging
            logger.debug(f"Structured response: thinking={bool(thinking)}, command={bool(command)}, complete={task_complete}, full_response={structured_response}")
            
            # If we have thinking but no command and task is not complete, 
            # the AI might be waiting or the response might be incomplete
            if thinking and not command and not task_complete:
                logger.debug("AI provided thinking but no command - may need to investigate or provide information")
            
        except (OllamaAPIError, OllamaConnectionError) as e:
            # Fallback to legacy format if structured outputs fail
            logger.warning(f"Structured outputs failed, using legacy format: {e}")
            use_structured = False
            
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
        
        if command:
            # Command found - show command and execute
            # Note: thinking already displayed above for structured outputs
            if not use_structured and thinking:
                print_thinking(thinking)
            
            # Show command
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
            try:
                returncode, stdout, stderr = executor.execute_command(
                    command, confirm=False, show_output=True, allow_sudo=allow_sudo, timeout=timeout
                )
                
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

