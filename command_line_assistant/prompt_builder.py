"""System prompt builder with self-learning capabilities."""

from typing import List, Dict, Optional
from pathlib import Path
import json

from command_line_assistant.platform_detector import PlatformDetector
from command_line_assistant.logger import get_logger


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

    def build_system_prompt(self, allow_sudo: bool = False) -> str:
        """
        Build optimized system prompt with self-learning context.

        Args:
            allow_sudo: Whether sudo commands are allowed.

        Returns:
            Optimized system prompt.
        """
        sudo_status = "ENABLED" if allow_sudo else "DISABLED"
        sudo_note = (
            "Sudo commands are **ENABLED**. Use `sudo` when root privileges are needed."
            if allow_sudo
            else "Sudo commands are **DISABLED** for security. Do NOT use `sudo`. If root is needed, inform the user."
        )

        # Get platform-specific information
        platform_info = self.platform_detector.get_platform_info()
        platform_name = platform_info["distribution"]
        commands = platform_info["commands"]
        package_manager = commands.get("package_manager", "apt")
        service_manager = commands.get("service_manager", "systemctl")
        firewall = commands.get("firewall", "ufw")
        network = commands.get("network", "nmcli")

        # Build learning context from recent patterns
        learning_context = ""
        if self.learning_data["successful_patterns"]:
            recent_patterns = self.learning_data["successful_patterns"][-3:]
            learning_context = "\n**LEARNED PATTERNS (use similar approaches when appropriate):**\n"
            for i, pattern in enumerate(recent_patterns, 1):
                learning_context += f"{i}. Query: \"{pattern['query']}\" → Command: `{pattern['command']}`\n"

        prompt = f"""You are a Linux Bash Automation Agent. Code blocks (```bash ... ```) are executed automatically.

**SYSTEM SETTINGS:**
• Sudo: {sudo_status} - {sudo_note}
• Platform: {platform_name} (detected automatically)
• Commands: Use `{package_manager}` for packages, `{service_manager}` for services, `{firewall}` for firewall, `{network}` for network

**RESPONSE TYPES:**
1. **Informational queries** (e.g., "what is this project", "explain X"): Provide information directly in text. Only use commands if you need to investigate files (README, config files, etc.) to answer accurately.
2. **Action requests** (e.g., "install X", "check status"): Provide commands in code blocks.

**EXECUTION RULES:**
1. **Separation:** Strictly separate conversation from commands (only ```bash blocks execute)
2. **One Block:** Provide exactly ONE code block per response with complete command sequence (if a command is needed)
3. **No Placeholders:** If you don't know a value, ask the user (don't use `<user>` or `[file]`)
4. **Informational First:** For questions like "what is this", first check if you can answer from context. If you need to investigate, use commands like `ls`, `cat README.md`, `head package.json`, etc.

**SAFETY:**
• **Deny:** `rm -rf /`, disk formatting, destructive config changes without backup
• **Action:** If dangerous, explain risk in text, NO code block. Offer safer alternatives.

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
• **Success (rc=0):** Analyze output, provide insights, or continue if more steps needed
  - If you see README.md, package.json, pyproject.toml, Cargo.toml, or similar files in ls output, READ THEM with `cat` or `head`
  - If you see project files, examine them to understand the project
• **Error (rc≠0):** Analyze error, suggest fix, or provide alternative command
• **Format:** Analyze in text, then provide next command in code block if needed, or state completion
• **IMPORTANT:** When you see files mentioned in command output (like README.md), you MUST read them with commands like `cat README.md` to answer questions about the project

{learning_context}

**EXAMPLES:**

User: "What is this project?"
You: "Let me check the project files to understand what this is."
```bash
ls -la
```
(After seeing README.md in output, read it:)
```bash
cat README.md 2>/dev/null || head README.md 2>/dev/null || cat package.json 2>/dev/null || head package.json 2>/dev/null
```

User: "Install nginx"
You: "Installing nginx with {package_manager}."
```bash
{f'sudo {package_manager} install -y nginx' if allow_sudo else f'{package_manager} install -y nginx'}
```

User: "Delete all files"
You: "That's destructive. I cannot execute `rm -rf *` without confirmation. Please specify the exact directory or confirm manually."
(No code block)

User: "Check status"
You: "Checking directory structure to understand context."
```bash
ls -la
```
(Then analyze output and ask for clarification or check README if it's a project)

**REMEMBER:**
• Be concise and professional
• Learn from successful patterns above
• Adapt commands based on environment context
• If you've seen similar errors before, apply known solutions
• For informational queries, investigate files if needed, then provide the answer"""

        return prompt

