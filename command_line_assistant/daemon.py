"""Daemon service for command-line-assistant."""

import sys
import signal
from pathlib import Path
from typing import Optional

from command_line_assistant.config import get_config, ConfigurationError
from command_line_assistant.client import OllamaClient
from command_line_assistant.exceptions import CommandLineAssistantError
from command_line_assistant.logger import get_logger


class Daemon:
    """Daemon service for command-line-assistant."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize daemon.

        Args:
            config_path: Optional path to config file.
        """
        self.config_path = config_path
        self.config = None
        self.client = None
        self.running = False
        self.logger = get_logger(f"{__name__}.Daemon")

    def _load_config(self) -> None:
        """Load configuration."""
        try:
            self.config = get_config(config_path=self.config_path)
            self.logger.info(f"Loaded config from {self.config.config_path or 'defaults'}")
        except ConfigurationError as e:
            self.logger.error(f"Configuration error: {e}")
            raise

    def _initialize_client(self) -> None:
        """Initialize Ollama client."""
        try:
            self.client = OllamaClient(self.config)
            self.logger.info(
                f"Initialized Ollama client: {self.client.endpoint}, "
                f"model: {self.client.model}"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize Ollama client: {e}")
            raise

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def start(self) -> None:
        """Start the daemon."""
        self.logger.info("Starting command-line-assistant daemon")

        # Load configuration
        self._load_config()

        # Initialize client
        self._initialize_client()

        # Test connection
        if not self.client.test_connection():
            self.logger.warning("Ollama connection test failed, but continuing...")

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self.running = True
        self.logger.info("Daemon started successfully")

        # Main loop
        try:
            import time
            while self.running:
                # For now, the daemon just runs and waits
                # In a full implementation, this could process requests from a queue
                # or socket activation
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the daemon."""
        self.logger.info("Stopping daemon")
        self.running = False

    def run(self) -> None:
        """Run the daemon (entry point)."""
        try:
            self.start()
        except CommandLineAssistantError as e:
            self.logger.error(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            sys.exit(1)


def main() -> None:
    """Main entry point for daemon."""
    import argparse

    parser = argparse.ArgumentParser(description="Command-line-assistant daemon")
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        help="Path to configuration file",
    )
    args = parser.parse_args()

    daemon = Daemon(config_path=args.config)
    daemon.run()


if __name__ == "__main__":
    main()

