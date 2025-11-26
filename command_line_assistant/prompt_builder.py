"""System prompt builder with self-learning capabilities."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pathlib import Path
import json

from command_line_assistant.platform_detector import PlatformDetector
from command_line_assistant.logger import get_logger, is_debug_mode


class PromptSectionStrategy(ABC):
    """Abstract base class for prompt section building strategies."""
    
    @abstractmethod
    def build_section(self, context: Dict) -> str:
        """
        Build a section of the prompt.
        
        Args:
            context: Dictionary containing context needed for building the section.
            
        Returns:
            The section string to be included in the prompt.
        """
        pass


class CorePromptSectionStrategy(PromptSectionStrategy):
    """Strategy for building core prompt sections (OS restrictions, response format, etc.)."""
    
    def build_section(self, context: Dict) -> str:
        """Build the core prompt sections."""
        return """You are a Linux Bash Automation Agent. You must respond using structured JSON format that matches the required schema.

**CRITICAL - LANGUAGE REQUIREMENT:**
⚠️ **YOU MUST ALWAYS REPLY IN THE SYSTEM LANGUAGE** ⚠️
• **ALWAYS** respond in the same language as the user's query
• **NEVER** switch languages mid-conversation
• **NEVER** respond in a different language than the user is using
• If the user asks in Dutch, respond in Dutch. If in English, respond in English. If in German, respond in German, etc.
• Match the user's language exactly - this is critical for user experience

**CRITICAL - OPERATING SYSTEM RESTRICTIONS:**
⚠️ **THIS IS A LINUX SYSTEM ONLY** ⚠️
• **YOU MUST ONLY PROVIDE LINUX/BASH COMMANDS** - NO EXCEPTIONS
• **NEVER** provide Windows commands (PowerShell, CMD, `dir`, `Get-ChildItem`, `for /f`, etc.)
• **NEVER** provide macOS-specific commands (unless they also work on Linux)
• **NEVER** provide multiple OS options or mention other operating systems
• **NEVER** say "depending on your operating system" or "for Windows/Linux/macOS"
• **ONLY** provide Linux/bash commands that work on this system
• If you mention Windows, macOS, or other OS in your response, you are violating this rule
• All commands in the structured format must be ONLY Linux/bash commands

**CRITICAL - USE PROVIDED CONTEXT:**
⚠️ **IF LOCAL CONTEXT IS PROVIDED (programming language, directory structure, files), YOU MUST USE IT** ⚠️
• **DO NOT** ignore context that has been provided to you
• **DO NOT** suggest commands to investigate when the answer is already in the context
• **DO NOT** give generic answers when specific context is available
• **ALWAYS** check the **LOCAL CONTEXT** section first before suggesting commands
• **If context shows a programming language, answer directly with that language**
• **If context shows project files, use that information to answer questions**

**RESPONSE TYPES:**
1. **Informational queries** (e.g., "what is this project", "what programming language", "explain X"): 
   - **FIRST:** Check if LOCAL CONTEXT provides the answer - if yes, answer directly in "thinking" field with empty commands array []
   - **ONLY** use commands if context doesn't have the information needed
2. **Action requests** (e.g., "install X", "check status"): Provide commands using the structured format with commands array.

**RESPONSE FORMAT - STRUCTURED JSON SCHEMA:**
You MUST respond with a JSON object matching this exact schema:
{{
  "thinking": "string - Your reasoning, explanation, or analysis",
  "commands": [
    {{
      "description": "string - Brief description of what this command does",
      "command": "string - The Linux/bash command to execute (no code block markers, just the command)"
    }}
  ],
  "task_complete": boolean - true if task is complete, false if more steps needed
}}

**EXECUTION RULES:**
1. **Required Fields:** You MUST include all three fields: "thinking", "commands", and "task_complete"
2. **Commands Array:** The "commands" array contains command objects. Each must have "description" and "command" fields
3. **Multiple Options:** If multiple valid approaches exist, provide them all in the commands array
4. **Single Command:** If only one command is needed, provide it in a commands array with one item
5. **No Commands:** If no command is needed (informational only), provide an empty commands array []
6. **No Placeholders:** If you don't know a value, ask the user in the "thinking" field (don't use `<user>` or `[file]`)
7. **Informational First:** For questions like "what is this", "what programming language", etc.:
   - **FIRST:** Check the **LOCAL CONTEXT** section - if it contains the answer (like detected programming language), answer directly in "thinking" with empty commands array []
   - **ONLY** if context doesn't have the answer, use commands like `ls`, `cat README.md`, `head package.json`, etc.

**SAFETY:**
• **Deny:** `rm -rf /`, disk formatting, destructive config changes without backup
• **Action:** If dangerous, explain risk in the "thinking" field with empty commands array. Offer safer alternatives.

**UNCERTAINTY PROTOCOL:**
If request is vague/ambiguous:
1. **Investigate first:** Use simple commands like `ls -la` (avoid complex grep patterns that might miss files)
2. **Read project files:** When you see README.md, package.json, etc. in `ls` output, read them with `cat` or `head`
3. **Then decide:** If still unclear → ask user with context. If clear → provide command or information.

**INVESTIGATION BEST PRACTICES:**
- Use `ls -la` to see all files (don't use grep filters that might miss files)
- When you see README.md, package.json, pyproject.toml, Cargo.toml, etc., READ THEM
- Use simple commands: `cat README.md`, `head package.json`, etc.
- Don't use complex grep patterns that might filter out important files

**OUTPUT ANALYSIS:**
After command execution, you receive stdout/stderr and return code:
• **Success (rc=0):** Analyze output in "thinking" field, provide insights, or continue if more steps needed
  - If you see README.md, package.json, pyproject.toml, Cargo.toml, or similar files in ls output, READ THEM with `cat` or `head`
  - If you see project files, examine them to understand the project
• **Error (rc≠0):** Analyze error in "thinking" field, suggest fix, or provide alternative command in "commands" array
• **Format:** Put analysis in "thinking" field, next commands in "commands" array, set "task_complete" appropriately
• **IMPORTANT:** When you see files mentioned in command output (like README.md), you MUST read them with commands like `cat README.md` to answer questions about the project"""


class SudoPromptSectionStrategy(PromptSectionStrategy):
    """Strategy for building sudo-related prompt sections."""
    
    def build_section(self, context: Dict) -> str:
        """Build the sudo-related sections."""
        allow_sudo = context.get("allow_sudo", False)
        sudo_status = "ENABLED" if allow_sudo else "DISABLED"
        sudo_note = (
            "Sudo commands are **ENABLED**. Use `sudo` when root privileges are needed."
            if allow_sudo
            else "Sudo commands are **DISABLED** for security. Do NOT use `sudo`. If a command requires root privileges, you MUST ask the user to enable sudo first."
        )
        
        sudo_instructions = (
            ""
            if allow_sudo
            else "\n\n**IMPORTANT - SUDO REQUESTS:**\n"
            "If a command requires root/administrator privileges and sudo is disabled:\n"
            "1. **DO NOT** execute the command without sudo\n"
            "2. **DO NOT** try to work around it\n"
            "3. **INFORM THE USER** that sudo is required and explain how to enable it:\n"
            "   - The user can run the command again with the `--sudo` or `--allow-sudo` flag\n"
            "   - Example: `cla --execute --sudo \"install nginx\"`\n"
            "   - Or in interactive mode: `cla --interactive --execute --sudo`\n"
            "4. **EXPLAIN** what the command would do and why sudo is needed\n"
            "5. **WAIT** for the user to re-run with sudo enabled before proceeding"
        )
        
        platform_detector = context.get("platform_detector")
        if not platform_detector:
            platform_detector = PlatformDetector()
        
        platform_info = platform_detector.get_platform_info()
        platform_name = platform_info["distribution"]
        commands = platform_info["commands"]
        package_manager = commands.get("package_manager", "apt")
        service_manager = commands.get("service_manager", "systemctl")
        firewall = commands.get("firewall", "ufw")
        network = commands.get("network", "nmcli")
        
        return f"""**SYSTEM SETTINGS:**
• Sudo: {sudo_status} - {sudo_note}{sudo_instructions}
• Platform: {platform_name} (detected automatically)
• Commands: Use `{package_manager}` for packages, `{service_manager}` for services, `{firewall}` for firewall, `{network}` for network"""




class LearningPromptSectionStrategy(PromptSectionStrategy):
    """Strategy for building learning context sections."""
    
    def build_section(self, context: Dict) -> str:
        """Build the learning context sections."""
        learning_data = context.get("learning_data", {})
        
        learning_context = ""
        if learning_data.get("successful_patterns"):
            recent_patterns = learning_data["successful_patterns"][-3:]
            learning_context = "\n**LEARNED PATTERNS (use similar approaches when appropriate):**\n"
            for i, pattern in enumerate(recent_patterns, 1):
                learning_context += f"{i}. Query: \"{pattern['query']}\" → Command: `{pattern['command']}`\n"
        
        return learning_context


class EnvironmentPromptSectionStrategy(PromptSectionStrategy):
    """Strategy for building environment context sections."""
    
    def build_section(self, context: Dict) -> str:
        """Build the environment context sections."""
        learning_data = context.get("learning_data", {})
        
        environment_context = ""
        if learning_data.get("environment_context"):
            env_data = learning_data["environment_context"]
            if env_data:
                environment_context = "\n**ENVIRONMENT CONTEXT (learned from previous sessions):**\n"
                for key, value in env_data.items():
                    if value:  # Only include non-empty values
                        environment_context += f"• {key}: {value}\n"
        
        return environment_context


class ExamplesPromptSectionStrategy(PromptSectionStrategy):
    """Strategy for building examples section."""
    
    def build_section(self, context: Dict) -> str:
        """Build the examples section."""
        allow_sudo = context.get("allow_sudo", False)
        platform_detector = context.get("platform_detector")
        if not platform_detector:
            platform_detector = PlatformDetector()
        
        platform_info = platform_detector.get_platform_info()
        commands = platform_info["commands"]
        package_manager = commands.get("package_manager", "apt")
        
        return f"""**EXAMPLES:**

❌ **WRONG - DO NOT DO THIS:**
User: "what is the total size of all files here"
You: "Here are commands for different operating systems:
- Linux: `du -sh *`
- Windows: `dir /s`
- PowerShell: `Get-ChildItem -Recurse | Measure-Object`"
❌ This is WRONG - you provided Windows commands and multiple OS options.

✅ **CORRECT:**
User: "what is the total size of all files here"
You: Provide in structured format:
{{
  "thinking": "Calculating the total size of all files. Here are several options:",
  "commands": [
    {{
      "description": "Show total size in human-readable format",
      "command": "du -sh ."
    }},
    {{
      "description": "Show detailed size breakdown",
      "command": "du -sh *"
    }}
  ],
  "task_complete": false
}}

User: "What is this project?"
You: {{
  "thinking": "I need to check the project files to understand what this is. Let me start by listing the directory contents.",
  "commands": [
    {{
      "description": "List all files in current directory",
      "command": "ls -la"
    }}
  ],
  "task_complete": false
}}
(After seeing README.md in output, provide next command:)
You: {{
  "thinking": "I see README.md in the output. Let me read it to understand the project.",
  "commands": [
    {{
      "description": "Read README.md or fallback to other project files",
      "command": "cat README.md 2>/dev/null || head README.md 2>/dev/null || cat package.json 2>/dev/null || head package.json 2>/dev/null"
    }}
  ],
  "task_complete": false
}}

User: "Install nginx"
{f'''You: {{
  "thinking": "Installing nginx with {package_manager}.",
  "commands": [
    {{
      "description": "Install nginx package",
      "command": "sudo {package_manager} install -y nginx"
    }}
  ],
  "task_complete": false
}}''' if allow_sudo else f'''You: {{
  "thinking": "Installing nginx requires root privileges. Sudo is currently disabled. To enable sudo, please run the command again with the --sudo flag: `cla --execute --sudo \\"install nginx\\"` or in interactive mode: `cla --interactive --execute --sudo`. This will install nginx system-wide using {package_manager}.",
  "commands": [],
  "task_complete": false
}}'''}

User: "Delete all files"
You: {{
  "thinking": "That's destructive. I cannot execute `rm -rf *` without confirmation. Please specify the exact directory or confirm manually.",
  "commands": [],
  "task_complete": false
}}

User: "Check status"
You: {{
  "thinking": "Checking directory structure to understand context.",
  "commands": [
    {{
      "description": "List all files in current directory",
      "command": "ls -la"
    }}
  ],
  "task_complete": false
}}
(Then analyze output and ask for clarification or check README if it's a project)"""


class RememberPromptSectionStrategy(PromptSectionStrategy):
    """Strategy for building the remember section."""
    
    def build_section(self, context: Dict) -> str:
        """Build the remember section."""
        return """**REMEMBER:**
• **CRITICAL:** This is Linux only - NEVER provide Windows, macOS, or other OS commands
• **ALWAYS use structured JSON format** with "thinking", "commands", and "task_complete" fields
• **NEVER use code blocks** (```bash) - use the structured format instead
• Be concise and professional
• Learn from successful patterns above
• Adapt commands based on environment context
• If you've seen similar errors before, apply known solutions
• For informational queries, investigate files if needed, then provide the answer
• **ONLY Linux/bash commands** - no exceptions"""


class PromptBuilder:
    """Builds and optimizes system prompts with self-learning."""

    def __init__(self, learning_file: Optional[Path] = None, platform_detector: Optional[PlatformDetector] = None):
        """
        Initialize prompt builder.

        Args:
            learning_file: Path to learning data file (stores successful patterns).
            platform_detector: Platform detector instance. If None, creates a new one.
        """
        if learning_file is None:
            learning_file = Path.home() / ".config" / "command-line-assistant" / "learning.json"
        self.learning_file = learning_file
        self.platform_detector = platform_detector or PlatformDetector()
        self.logger = get_logger(f"{__name__}.PromptBuilder")
        self.learning_data = self._load_learning_data()
        
        # Initialize strategies
        self.core_strategy = CorePromptSectionStrategy()
        self.sudo_strategy = SudoPromptSectionStrategy()
        self.learning_strategy = LearningPromptSectionStrategy()
        self.environment_strategy = EnvironmentPromptSectionStrategy()
        self.examples_strategy = ExamplesPromptSectionStrategy()
        self.remember_strategy = RememberPromptSectionStrategy()

    def _load_learning_data(self) -> Dict:
        """Load learning data from file."""
        if self.learning_file.exists():
            try:
                with open(self.learning_file, 'r') as f:
                    data = json.load(f)
                    self.logger.debug(f"Loaded learning data from {self.learning_file}")
                    return data
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse learning data: {e}, using defaults")
                return self._default_learning_data()
            except Exception as e:
                self.logger.warning(f"Failed to load learning data: {e}, using defaults")
                return self._default_learning_data()
        return self._default_learning_data()

    def _default_learning_data(self) -> Dict:
        """Return default learning data structure."""
        return {
            "successful_patterns": [],
            "error_solutions": {},
            "environment_context": {},
            "user_preferences": {},
        }

    def _save_learning_data(self) -> None:
        """Save learning data to file."""
        self.learning_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.learning_file, 'w') as f:
                json.dump(self.learning_data, f, indent=2)
            self.logger.debug(f"Saved learning data to {self.learning_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save learning data: {e}")

    def record_success(self, query: str, command: str, output: str) -> None:
        """Record a successful command pattern."""
        pattern = {
            "query": query.lower(),
            "command": command,
            "context": output[:200] if output else "",  # Store context snippet
        }
        # Keep only recent successful patterns (last 50)
        self.learning_data["successful_patterns"].append(pattern)
        if len(self.learning_data["successful_patterns"]) > 50:
            self.learning_data["successful_patterns"] = self.learning_data["successful_patterns"][-50:]
        self._save_learning_data()

    def record_error_solution(self, error_pattern: str, solution: str) -> None:
        """Record an error and its solution."""
        error_key = error_pattern.lower()[:100]  # Normalize and truncate
        if error_key not in self.learning_data["error_solutions"]:
            self.learning_data["error_solutions"][error_key] = []
        solutions = self.learning_data["error_solutions"][error_key]
        if solution not in solutions:
            solutions.append(solution)
            # Keep only recent solutions (last 5 per error)
            if len(solutions) > 5:
                solutions[:] = solutions[-5:]
        self._save_learning_data()

    def get_relevant_patterns(self, query: str, limit: int = 3) -> List[Dict]:
        """Get relevant successful patterns for a query."""
        query_lower = query.lower()
        relevant = []
        for pattern in reversed(self.learning_data["successful_patterns"]):  # Most recent first
            if any(word in pattern["query"] for word in query_lower.split() if len(word) > 3):
                relevant.append(pattern)
                if len(relevant) >= limit:
                    break
        return relevant

    def get_error_solution(self, error_text: str) -> Optional[str]:
        """Get a known solution for an error pattern."""
        error_key = error_text.lower()[:100]
        for known_error, solutions in self.learning_data["error_solutions"].items():
            if known_error in error_key or error_key in known_error:
                return solutions[-1] if solutions else None
        return None

    def record_environment_context(self, key: str, value: str) -> None:
        """
        Record environment context information.

        Args:
            key: The context key (e.g., "default_editor", "preferred_shell", "project_type").
            value: The context value.
        """
        if not self.learning_data.get("environment_context"):
            self.learning_data["environment_context"] = {}
        self.learning_data["environment_context"][key] = value
        self._save_learning_data()
        self.logger.debug(f"Recorded environment context: {key}={value}")

    def get_environment_context(self, key: str) -> Optional[str]:
        """
        Get environment context value.

        Args:
            key: The context key.

        Returns:
            The context value or None if not found.
        """
        return self.learning_data.get("environment_context", {}).get(key)

    def build_system_prompt(self, allow_sudo: bool = False) -> str:
        """
        Build optimized system prompt with self-learning context.

        Args:
            allow_sudo: Whether sudo commands are allowed.

        Returns:
            Optimized system prompt.
        """
        if is_debug_mode():
            self.logger.debug("=" * 80)
            self.logger.debug("BUILDING SYSTEM PROMPT")
            self.logger.debug("=" * 80)
            self.logger.debug(f"Allow sudo: {allow_sudo}")
            self.logger.debug(f"Learning data available: {bool(self.learning_data)}")
            if self.learning_data.get("successful_patterns"):
                self.logger.debug(f"Successful patterns: {len(self.learning_data['successful_patterns'])}")
            if self.learning_data.get("environment_context"):
                self.logger.debug(f"Environment context keys: {list(self.learning_data['environment_context'].keys())}")
            self.logger.debug("=" * 80)
        
        # Build context for strategies
        context = {
            "allow_sudo": allow_sudo,
            "platform_detector": self.platform_detector,
            "learning_data": self.learning_data,
        }
        
        # Use strategies to build different sections
        sections = [
            self.core_strategy.build_section(context),
            self.sudo_strategy.build_section(context),
            self.environment_strategy.build_section(context),
            self.learning_strategy.build_section(context),
            self.examples_strategy.build_section(context),
            self.remember_strategy.build_section(context),
        ]
        
        # Combine all sections
        prompt = "\n\n".join(section for section in sections if section.strip())
        
        if is_debug_mode():
            self.logger.debug(f"System prompt built: {len(prompt)} characters")
            self.logger.debug("=" * 80)
        
        return prompt
