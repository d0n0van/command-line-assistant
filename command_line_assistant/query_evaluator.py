"""Query evaluation module for determining if a query needs local context.

Uses Strategy pattern to allow different evaluation strategies.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from command_line_assistant.logger import get_logger, is_debug_mode


@dataclass
class QueryContext:
    """Context information about a query."""
    needs_local_context: bool
    target_path: Optional[Path]
    query_type: str


class EvaluationStrategy(ABC):
    """Abstract base class for query evaluation strategies."""

    @abstractmethod
    def evaluate(self, query: str, cwd: Path) -> Optional[QueryContext]:
        """
        Evaluate a query using this strategy.

        Args:
            query: The user query to evaluate.
            cwd: Current working directory.

        Returns:
            QueryContext if this strategy determines context is needed, None otherwise.
        """
        pass


class PathDetectionStrategy(EvaluationStrategy):
    """Strategy that detects explicit paths in queries."""

    # Path patterns (absolute and relative)
    PATH_PATTERN = re.compile(
        r'(?:^|\s)(?:'
        r'/[^\s]+'  # Absolute paths starting with /
        r'|\.\.?/[^\s]+'  # Relative paths with ./ or ../
        r'|~/[^\s]+'  # Home directory paths
        r'|[A-Z]:\\[^\s]+'  # Windows paths
        r')(?:\s|$)'
    )

    def __init__(self):
        """Initialize path detection strategy."""
        self.logger = get_logger(f"{__name__}.PathDetectionStrategy")

    def evaluate(self, query: str, cwd: Path) -> Optional[QueryContext]:
        """Evaluate query for explicit paths."""
        target_path = self._extract_path(query, cwd)
        
        if target_path:
            self.logger.debug(f"Path detected: {target_path}")
            return QueryContext(
                needs_local_context=True,
                target_path=target_path,
                query_type="file_operation"
            )
        return None

    def _extract_path(self, query: str, cwd: Path) -> Optional[Path]:
        """Extract path from query if present."""
        matches = self.PATH_PATTERN.findall(query)
        if not matches:
            return None

        for match in matches:
            path_str = match.strip()
            path_str = re.sub(r'^["\']|["\']$', '', path_str)
            path_str = path_str.strip()

            if not path_str:
                continue

            try:
                if path_str.startswith('~'):
                    path = Path(path_str).expanduser()
                else:
                    path = Path(path_str)

                if not path.is_absolute():
                    path = (cwd / path).resolve()
                else:
                    path = path.resolve()

                if path.exists():
                    return path
                if '/' in path_str or '\\' in path_str:
                    return path

            except (ValueError, OSError) as e:
                self.logger.debug(f"Failed to parse path '{path_str}': {e}")
                continue

        return None


class KeywordDetectionStrategy(EvaluationStrategy):
    """Strategy that detects project-related keywords in queries."""

    # Keywords that suggest local context is needed
    LOCAL_CONTEXT_KEYWORDS = [
        "project", "directory", "folder", "file", "code", "repository",
        "repo", "codebase", "workspace", "workspace", "source", "src",
        "module", "package", "component", "structure", "tree",
        "language", "programming", "framework", "library", "dependencies"
    ]

    def __init__(self):
        """Initialize keyword detection strategy."""
        self.logger = get_logger(f"{__name__}.KeywordDetectionStrategy")

    def evaluate(self, query: str, cwd: Path) -> Optional[QueryContext]:
        """Evaluate query for project-related keywords."""
        query_lower = query.lower().strip()
        has_keywords = any(keyword in query_lower for keyword in self.LOCAL_CONTEXT_KEYWORDS)

        if has_keywords:
            self.logger.debug("Project-related keywords detected")
            return QueryContext(
                needs_local_context=True,
                target_path=cwd,
                query_type="project_info"
            )
        return None


class PatternDetectionStrategy(EvaluationStrategy):
    """Strategy that detects project-related question patterns."""

    # Question patterns that suggest project-related queries
    PROJECT_QUESTION_PATTERNS = [
        r"what\s+is\s+(this|the|that)\s+(project|code|codebase|repository|repo)",
        r"explain\s+(this|the|that)\s+(project|code|codebase|repository|repo)",
        r"describe\s+(this|the|that)\s+(project|code|codebase|repository|repo)",
        r"analyze\s+(this|the|that)\s+(project|code|codebase|repository|repo)",
        r"what\s+(does|is)\s+(this|the|that)\s+(project|code|codebase|repository|repo)",
        r"what\s+(programming\s+)?language",
        r"which\s+(programming\s+)?language",
        r"what\s+framework",
        r"what\s+technology",
    ]

    def __init__(self):
        """Initialize pattern detection strategy."""
        self.logger = get_logger(f"{__name__}.PatternDetectionStrategy")

    def evaluate(self, query: str, cwd: Path) -> Optional[QueryContext]:
        """Evaluate query for project-related question patterns."""
        query_lower = query.lower().strip()
        
        has_project_question = any(
            re.search(pattern, query_lower, re.IGNORECASE)
            for pattern in self.PROJECT_QUESTION_PATTERNS
        )

        if has_project_question:
            self.logger.debug("Project-related question pattern detected")
            return QueryContext(
                needs_local_context=True,
                target_path=cwd,
                query_type="project_info"
            )
        return None


class OllamaStrategySelector(EvaluationStrategy):
    """Strategy that uses Ollama AI to select the best evaluation strategy."""

    def __init__(self, ollama_client=None):
        """
        Initialize Ollama strategy selector.

        Args:
            ollama_client: OllamaClient instance. If None, will be created when needed.
        """
        self.logger = get_logger(f"{__name__}.OllamaStrategySelector")
        self.ollama_client = ollama_client
        self._fallback_strategies = {
            "path_detection": PathDetectionStrategy(),
            "pattern_detection": PatternDetectionStrategy(),
            "keyword_detection": KeywordDetectionStrategy(),
        }

    def _get_client(self):
        """Get or create Ollama client."""
        if self.ollama_client is None:
            from command_line_assistant.client import OllamaClient
            self.ollama_client = OllamaClient()
        return self.ollama_client

    def evaluate(self, query: str, cwd: Path) -> Optional[QueryContext]:
        """Use Ollama to select the best strategy and evaluate."""
        try:
            if is_debug_mode():
                self.logger.debug("=" * 80)
                self.logger.debug("QUERY EVALUATION: Using Ollama strategy selector")
                self.logger.debug("=" * 80)
                self.logger.debug(f"Query: {query}")
                self.logger.debug(f"Current working directory: {cwd}")
                self.logger.debug("Reason: Determining if query needs local file/project context")
                self.logger.debug("=" * 80)
            client = self._get_client()
            from command_line_assistant.schemas import get_strategy_selection_schema

            system_prompt = """You are a query analysis assistant. Analyze user queries to determine if they need local file/project context.

Available strategies:
- path_detection: Use when query contains explicit file/directory paths (e.g., "/home/user/project", "./src", "~/myfile")
- pattern_detection: Use when query matches project-related question patterns (e.g., "what is this project", "explain this codebase")
- keyword_detection: Use when query contains project-related keywords (e.g., "project", "repository", "codebase", "directory")
- none: Use when query is general and doesn't need local context (e.g., "install nginx", "check disk usage")

Analyze the query and select the most appropriate strategy. If a path is detected, extract it."""

            user_prompt = f"""Analyze this query and determine which evaluation strategy to use:

Query: "{query}"
Current working directory: {cwd}

Select the best strategy and provide the evaluation result."""

            schema = get_strategy_selection_schema()
            response = client.generate_structured(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                format_schema=schema,
                stream=False
            )
            
            if is_debug_mode():
                self.logger.debug("Ollama strategy selection response received")

            selected_strategy = response.get("selected_strategy", "none")
            needs_local_context = response.get("needs_local_context", False)
            target_path_str = response.get("target_path")
            query_type = response.get("query_type", "general")

            self.logger.debug(
                f"Ollama selected strategy: {selected_strategy}, "
                f"needs_context={needs_local_context}, reasoning={response.get('reasoning', '')}"
            )

            # If Ollama says no context needed, return None
            if not needs_local_context or selected_strategy == "none":
                return None

            # Parse target path if provided
            target_path = None
            if target_path_str:
                try:
                    target_path = Path(target_path_str)
                    if not target_path.is_absolute():
                        target_path = (cwd / target_path).resolve()
                    else:
                        target_path = target_path.resolve()
                except (ValueError, OSError) as e:
                    self.logger.debug(f"Failed to parse target path '{target_path_str}': {e}")
                    # Fall back to using the selected strategy
                    if selected_strategy in self._fallback_strategies:
                        return self._fallback_strategies[selected_strategy].evaluate(query, cwd)

            # If no target path but context needed, use cwd
            if target_path is None:
                target_path = cwd

            return QueryContext(
                needs_local_context=needs_local_context,
                target_path=target_path,
                query_type=query_type
            )

        except Exception as e:
            # If Ollama fails, fall back to traditional strategies
            self.logger.warning(f"Ollama strategy selection failed: {e}, falling back to traditional strategies")
            return None


class QueryEvaluator:
    """Evaluates queries using multiple strategies.

    Uses Strategy pattern to allow different evaluation algorithms.
    The evaluator tries each strategy in order until one determines
    that local context is needed.
    """

    def __init__(self, strategies: Optional[list[EvaluationStrategy]] = None, use_ollama: bool = True, ollama_client=None):
        """
        Initialize query evaluator.

        Args:
            strategies: List of evaluation strategies to use.
                       If None, uses default strategies.
            use_ollama: Whether to use Ollama for strategy selection (default: True).
            ollama_client: OllamaClient instance for Ollama strategy (optional).
        """
        self.logger = get_logger(f"{__name__}.QueryEvaluator")
        
        # Default strategies if none provided
        if strategies is None:
            self.strategies = []
            
            # Add Ollama strategy first if enabled
            if use_ollama:
                try:
                    self.strategies.append(OllamaStrategySelector(ollama_client))
                except Exception as e:
                    self.logger.warning(f"Failed to initialize Ollama strategy: {e}, using traditional strategies only")
            
            # Add traditional strategies as fallback
            self.strategies.extend([
                PathDetectionStrategy(),
                PatternDetectionStrategy(),
                KeywordDetectionStrategy(),
            ])
        else:
            self.strategies = strategies

    def evaluate_query(self, query: str, cwd: Optional[Path] = None) -> QueryContext:
        """
        Evaluate a query to determine if it needs local context.

        Uses all configured strategies. The first strategy that determines
        context is needed wins. If no strategy matches, returns a context
        indicating no local context is needed.

        Args:
            query: The user query to evaluate.
            cwd: Current working directory (defaults to current directory).

        Returns:
            QueryContext with evaluation results.
        """
        if cwd is None:
            import os
            cwd = Path(os.getcwd())

        if is_debug_mode():
            self.logger.debug("=" * 80)
            self.logger.debug("QUERY EVALUATION: Starting evaluation")
            self.logger.debug("=" * 80)
            self.logger.debug(f"Query: {query}")
            self.logger.debug(f"Current working directory: {cwd}")
            self.logger.debug(f"Number of strategies: {len(self.strategies)}")
            for i, strategy in enumerate(self.strategies):
                self.logger.debug(f"  Strategy {i+1}: {strategy.__class__.__name__}")
            self.logger.debug("=" * 80)

        # Try each strategy in order
        for strategy in self.strategies:
            if is_debug_mode():
                self.logger.debug(f"Trying strategy: {strategy.__class__.__name__}")
            result = strategy.evaluate(query, cwd)
            if result and result.needs_local_context:
                self.logger.debug(
                    f"Strategy {strategy.__class__.__name__} determined context is needed: "
                    f"target_path={result.target_path}, type={result.query_type}"
                )
                if is_debug_mode():
                    self.logger.debug("=" * 80)
                    self.logger.debug("QUERY EVALUATION: Context needed")
                    self.logger.debug("=" * 80)
                return result

        # No strategy matched - no local context needed
        self.logger.debug("No strategy determined that local context is needed")
        if is_debug_mode():
            self.logger.debug("=" * 80)
            self.logger.debug("QUERY EVALUATION: No local context needed")
            self.logger.debug("=" * 80)
        return QueryContext(
            needs_local_context=False,
            target_path=None,
            query_type="general"
        )

    def add_strategy(self, strategy: EvaluationStrategy) -> None:
        """
        Add a new evaluation strategy.

        Args:
            strategy: The strategy to add.
        """
        self.strategies.append(strategy)
        self.logger.debug(f"Added strategy: {strategy.__class__.__name__}")

    def remove_strategy(self, strategy_type: type[EvaluationStrategy]) -> None:
        """
        Remove a strategy by type.

        Args:
            strategy_type: The type of strategy to remove.
        """
        self.strategies = [s for s in self.strategies if not isinstance(s, strategy_type)]
        self.logger.debug(f"Removed strategy: {strategy_type.__name__}")
