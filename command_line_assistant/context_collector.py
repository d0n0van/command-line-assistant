"""Context collection module for gathering directory tree and relevant files.

Uses Strategy pattern for different tree generation strategies.
"""

import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

from command_line_assistant.logger import get_logger


class TreeGenerationStrategy(ABC):
    """Abstract base class for tree generation strategies."""

    @abstractmethod
    def generate_tree(self, path: Path, max_depth: int) -> Optional[str]:
        """
        Generate directory tree structure.

        Args:
            path: Directory path to analyze.
            max_depth: Maximum depth for tree.

        Returns:
            Tree structure as string, or None if strategy cannot generate it.
        """
        pass


class CommandTreeStrategy(TreeGenerationStrategy):
    """Strategy that uses the 'tree' command if available."""

    def __init__(self):
        """Initialize command tree strategy."""
        self.logger = get_logger(f"{__name__}.CommandTreeStrategy")

    def generate_tree(self, path: Path, max_depth: int) -> Optional[str]:
        """Generate tree using 'tree' command."""
        if not path.exists() or not path.is_dir():
            return None

        try:
            result = subprocess.run(
                ["tree", "-L", str(max_depth), "-a", str(path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.logger.debug("Generated tree using 'tree' command")
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
            self.logger.debug(f"Tree command not available or failed: {e}")
        
        return None


class PythonTreeStrategy(TreeGenerationStrategy):
    """Strategy that generates tree using Python implementation."""

    def __init__(self):
        """Initialize Python tree strategy."""
        self.logger = get_logger(f"{__name__}.PythonTreeStrategy")

    def generate_tree(self, path: Path, max_depth: int) -> Optional[str]:
        """Generate tree using Python implementation."""
        if not path.exists() or not path.is_dir():
            return f"Path does not exist or is not a directory: {path}"

        lines = []
        prefix = ""

        def _walk(current_path: Path, current_prefix: str, current_depth: int):
            if current_depth > max_depth:
                return

            try:
                items = sorted(current_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
                for i, item in enumerate(items):
                    is_last = i == len(items) - 1
                    current_symbol = "└── " if is_last else "├── "
                    lines.append(f"{current_prefix}{current_symbol}{item.name}")

                    if item.is_dir() and current_depth < max_depth:
                        next_prefix = current_prefix + ("    " if is_last else "│   ")
                        _walk(item, next_prefix, current_depth + 1)
            except PermissionError:
                lines.append(f"{current_prefix}└── [Permission Denied]")

        _walk(path, prefix, 0)
        result = "\n".join(lines) if lines else f"{path.name}/"
        self.logger.debug("Generated tree using Python implementation")
        return result


class ContextCollector:
    """Collects directory tree structure and relevant context files.

    Uses Strategy pattern for tree generation - tries different strategies
    in order until one succeeds.
    """

    # README files to look for
    README_FILES = [
        "README.md", "README.txt", "README", "README.rst", "README.markdown",
        "readme.md", "readme.txt", "readme"
    ]

    # Config files to look for
    CONFIG_FILES = [
        "package.json", "pyproject.toml", "Cargo.toml", "pom.xml",
        "build.gradle", "setup.py", "requirements.txt", "Pipfile",
        "go.mod", "go.sum", "composer.json", "Gemfile", "Makefile",
        "CMakeLists.txt", "Dockerfile", "docker-compose.yml", ".gitignore",
        ".gitattributes", "tsconfig.json", "webpack.config.js", "vite.config.js"
    ]

    # Documentation files (in root only)
    DOC_FILES = [".md", ".txt", ".rst"]

    # Maximum lines to read per file
    MAX_FILE_LINES = 300

    def __init__(self, tree_strategies: Optional[List[TreeGenerationStrategy]] = None):
        """
        Initialize context collector.

        Args:
            tree_strategies: List of tree generation strategies to try.
                            If None, uses default strategies (command first, then Python).
        """
        self.logger = get_logger(f"{__name__}.ContextCollector")
        
        # Default strategies if none provided
        if tree_strategies is None:
            self.tree_strategies = [
                CommandTreeStrategy(),
                PythonTreeStrategy(),
            ]
        else:
            self.tree_strategies = tree_strategies

    def get_directory_tree(self, path: Path, max_depth: int = 4) -> str:
        """
        Get directory tree structure.

        Tries each tree generation strategy in order until one succeeds.

        Args:
            path: Directory path to analyze.
            max_depth: Maximum depth for tree (default: 4).

        Returns:
            Tree structure as string.
        """
        # Try each strategy in order
        for strategy in self.tree_strategies:
            result = strategy.generate_tree(path, max_depth)
            if result is not None:
                return result
        
        # Fallback if all strategies fail
        return f"Unable to generate tree for: {path}"

    def collect_context_files(self, path: Path) -> Dict[str, str]:
        """
        Collect relevant context files from a directory.

        Args:
            path: Directory path to analyze.

        Returns:
            Dictionary mapping filename to file content (first MAX_FILE_LINES).
        """
        context_files = {}

        if not path.exists():
            return context_files

        # If path is a file, just read that file
        if path.is_file():
            content = self._read_file_safe(path)
            if content:
                context_files[path.name] = content
            return context_files

        # Collect README files
        for readme_name in self.README_FILES:
            readme_path = path / readme_name
            if readme_path.exists() and readme_path.is_file():
                content = self._read_file_safe(readme_path)
                if content:
                    context_files[readme_name] = content
                    break  # Only take the first README found

        # Collect config files
        for config_name in self.CONFIG_FILES:
            config_path = path / config_name
            if config_path.exists() and config_path.is_file():
                content = self._read_file_safe(config_path)
                if content:
                    context_files[config_name] = content

        # Collect documentation files in root only
        try:
            for item in path.iterdir():
                if item.is_file() and any(item.name.endswith(ext) for ext in self.DOC_FILES):
                    # Skip if already collected as README
                    if item.name not in context_files:
                        content = self._read_file_safe(item)
                        if content:
                            context_files[item.name] = content
        except PermissionError:
            self.logger.warning(f"Permission denied reading directory: {path}")

        return context_files

    def _read_file_safe(self, file_path: Path) -> Optional[str]:
        """
        Safely read a file with line limit.

        Args:
            file_path: Path to file.

        Returns:
            File content (first MAX_FILE_LINES) or None if error.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= self.MAX_FILE_LINES:
                        lines.append(f"\n... (truncated after {self.MAX_FILE_LINES} lines)")
                        break
                    lines.append(line.rstrip('\n\r'))
                return '\n'.join(lines)
        except (IOError, OSError, UnicodeDecodeError) as e:
            self.logger.debug(f"Failed to read file {file_path}: {e}")
            return None

    def format_context_attachment(self, tree: str, files: Dict[str, str]) -> str:
        """
        Format tree and files as a context attachment.

        Args:
            tree: Directory tree structure.
            files: Dictionary of filename to content.

        Returns:
            Formatted context attachment string.
        """
        parts = ["**CONTEXT ATTACHMENTS:**\n"]

        # Add directory tree
        if tree:
            parts.append("**Directory Tree:**")
            parts.append("```")
            parts.append(tree)
            parts.append("```")
            parts.append("")

        # Add files
        if files:
            for filename, content in files.items():
                parts.append(f"**{filename}:**")
                parts.append("```")
                parts.append(content)
                parts.append("```")
                parts.append("")

        return "\n".join(parts)

    def add_tree_strategy(self, strategy: TreeGenerationStrategy, position: int = -1) -> None:
        """
        Add a new tree generation strategy.

        Args:
            strategy: The strategy to add.
            position: Position to insert at (-1 for end, 0 for beginning).
        """
        if position == -1:
            self.tree_strategies.append(strategy)
        else:
            self.tree_strategies.insert(position, strategy)
        self.logger.debug(f"Added tree strategy: {strategy.__class__.__name__}")

    def remove_tree_strategy(self, strategy_type: type[TreeGenerationStrategy]) -> None:
        """
        Remove a tree strategy by type.

        Args:
            strategy_type: The type of strategy to remove.
        """
        self.tree_strategies = [s for s in self.tree_strategies if not isinstance(s, strategy_type)]
        self.logger.debug(f"Removed tree strategy: {strategy_type.__name__}")
