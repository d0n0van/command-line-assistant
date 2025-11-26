"""Configuration management for command-line-assistant."""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from command_line_assistant.exceptions import ConfigurationError
from command_line_assistant.logger import get_logger
from command_line_assistant.sanitizer import InputSanitizer

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        raise ConfigurationError(
            "tomli is required for Python < 3.11. Install it with: pip install tomli"
        )


DEFAULT_CONFIG = {
    "ollama": {
        "endpoint": "http://localhost:11434/api/generate",
        "model": "mistral:instruct",
        "temperature": 0.7,
    }
}

CONFIG_DIRS = [
    Path("/etc/xdg/command-line-assistant"),
    Path.home() / ".config" / "command-line-assistant",
]

CONFIG_FILENAME = "config.toml"


class Config:
    """Configuration manager for command-line-assistant."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration.

        Args:
            config_path: Optional path to config file. If not provided,
                        searches standard locations.

        Raises:
            ConfigurationError: If configuration file is invalid or missing.
        """
        self._config: Dict[str, Any] = {}
        self._config_path: Optional[Path] = None
        self.logger = get_logger(f"{__name__}.Config")
        self.sanitizer = InputSanitizer()

        if config_path:
            self._config_path = Path(config_path)
            if not self._config_path.exists():
                raise ConfigurationError(f"Config file not found: {config_path}")
            self._load_config(self._config_path)
        else:
            self._load_from_standard_locations()

        self._apply_environment_overrides()
        self._validate_config()

    def _load_from_standard_locations(self) -> None:
        """Load configuration from standard locations."""
        for config_dir in CONFIG_DIRS:
            config_file = config_dir / CONFIG_FILENAME
            try:
                if config_file.exists():
                    self._config_path = config_file
                    self._load_config(config_file)
                    self.logger.info(f"Loaded config from {config_file}")
                    return
            except PermissionError:
                # Skip directories we don't have permission to access
                self.logger.debug(f"Permission denied accessing {config_file}")
                continue

        # No config found, use defaults
        self._config = DEFAULT_CONFIG.copy()
        self.logger.info("Using default configuration")

    def _load_config(self, config_path: Path) -> None:
        """
        Load configuration from a TOML file.

        Args:
            config_path: Path to the configuration file.

        Raises:
            ConfigurationError: If the file cannot be read or parsed.
        """
        try:
            with open(config_path, "rb") as f:
                self._config = tomllib.load(f)
            self.logger.debug(f"Successfully loaded config from {config_path}")
        except FileNotFoundError:
            raise ConfigurationError(f"Config file not found: {config_path}")
        except PermissionError as e:
            raise ConfigurationError(f"Permission denied reading config: {config_path}") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to load config from {config_path}: {e}") from e

    def _apply_environment_overrides(self) -> None:
        """Apply environment variable overrides."""
        env_mappings = {
            "OLLAMA_ENDPOINT": ("ollama", "endpoint"),
            "OLLAMA_MODEL": ("ollama", "model"),
            "OLLAMA_TEMPERATURE": ("ollama", "temperature"),
        }

        for env_var, (section, key) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                if section not in self._config:
                    self._config[section] = {}
                if key == "temperature":
                    try:
                        # Sanitize and validate temperature value
                        sanitized = self.sanitizer.sanitize_config_value(value, "number")
                        self._config[section][key] = float(sanitized)
                        self.logger.debug(f"Overrode {key} from {env_var}: {value}")
                    except ValueError as e:
                        raise ConfigurationError(
                            f"Invalid temperature value in {env_var}: {value}"
                        ) from e
                elif key == "endpoint":
                    # Sanitize URL
                    try:
                        self._config[section][key] = self.sanitizer.sanitize_config_value(value, "url")
                        self.logger.debug(f"Overrode {key} from {env_var}: {value}")
                    except ValueError as e:
                        raise ConfigurationError(
                            f"Invalid endpoint URL in {env_var}: {value}"
                        ) from e
                else:
                    # Sanitize string value
                    self._config[section][key] = self.sanitizer.sanitize_config_value(value, "string")
                    self.logger.debug(f"Overrode {key} from {env_var}: {value}")

    def _validate_config(self) -> None:
        """Validate configuration values."""
        if "ollama" not in self._config:
            self._config["ollama"] = {}

        ollama_config = self._config["ollama"]

        # Set defaults for missing values
        ollama_config.setdefault("endpoint", DEFAULT_CONFIG["ollama"]["endpoint"])
        ollama_config.setdefault("model", DEFAULT_CONFIG["ollama"]["model"])
        ollama_config.setdefault("temperature", DEFAULT_CONFIG["ollama"]["temperature"])

        # Validate temperature
        temp = ollama_config["temperature"]
        if not isinstance(temp, (int, float)) or not (0.0 <= temp <= 2.0):
            raise ConfigurationError(
                f"Temperature must be between 0.0 and 2.0, got: {temp}"
            )

        # Validate endpoint is a string
        if not isinstance(ollama_config["endpoint"], str):
            raise ConfigurationError("Ollama endpoint must be a string")

        # Validate model is a string
        if not isinstance(ollama_config["model"], str):
            raise ConfigurationError("Ollama model must be a string")

    @property
    def ollama_endpoint(self) -> str:
        """Get Ollama API endpoint."""
        return self._config["ollama"]["endpoint"]

    @property
    def ollama_model(self) -> str:
        """Get Ollama model name."""
        return self._config["ollama"]["model"]

    @property
    def ollama_temperature(self) -> float:
        """Get Ollama temperature setting."""
        return float(self._config["ollama"]["temperature"])

    @property
    def config_path(self) -> Optional[Path]:
        """Get path to loaded config file."""
        return self._config_path

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(section, {}).get(key, default)


def get_config(config_path: Optional[Path] = None) -> Config:
    """
    Get configuration instance.

    Args:
        config_path: Optional path to config file.

    Returns:
        Config instance.
    """
    return Config(config_path)

