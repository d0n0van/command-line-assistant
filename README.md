# Command Line Assistant

A production-ready command-line assistant powered by Ollama that provides AI-driven assistance for system administration and general tasks on Linux systems.

## Features

- **Interactive CLI Mode**: Conversational assistance with streaming responses
- **Single-Query Mode**: Quick one-off questions
- **Command Execution**: AI can execute commands with intelligent output analysis
- **Structured Outputs**: Uses Ollama's structured outputs for reliable command extraction
- **Platform Detection**: Automatically detects Linux distribution and uses appropriate commands
- **Self-Learning**: Learns from successful commands and error fixes
- **Safety Features**: Built-in protection with input sanitization and dangerous command blocking
- **Configurable**: Flexible configuration via TOML files or environment variables
- **Daemon Service**: Background service support for systemd

## Installation

### From Package (Recommended)

#### RPM (RHEL/Fedora/CentOS)

```bash
# Build RPM
make rpm

# Install
sudo dnf install ~/rpmbuild/RPMS/noarch/command-line-assistant-*.rpm
```

#### DEB (Debian/Ubuntu)

```bash
# Build DEB
make deb

# Install
sudo dpkg -i debuild/command-line-assistant_*.deb
```

#### Arch Linux

```bash
# Build package
make arch

# Install
sudo pacman -U archbuild/command-line-assistant-*.pkg.tar.zst
```

### From Source

1. **Install dependencies:**

```bash
pip install -r requirements.txt
```

2. **Install the package:**

```bash
pip install -e .
```

Or use the Makefile:

```bash
make install
```

## Quick Start

### Basic Usage

**Interactive mode:**

```bash
cla
```

**Single query:**

```bash
cla "How do I check disk usage?"
```

**Command execution mode:**

```bash
cla --execute "check disk usage"
```

### Configuration

Configuration is loaded from (in order of precedence):

1. Command-line options (`--model`, `--endpoint`, etc.)
2. Environment variables (`OLLAMA_MODEL`, `OLLAMA_ENDPOINT`, etc.)
3. User config: `~/.config/command-line-assistant/config.toml`
4. System config: `/etc/xdg/command-line-assistant/config.toml`
5. Default values

**Default configuration:**

```toml
[ollama]
endpoint = "http://localhost:11434/api/generate"
model = "mistral:instruct"
temperature = 0.7
```

**Environment variables:**

- `OLLAMA_ENDPOINT`: Override API endpoint
- `OLLAMA_MODEL`: Override model name
- `OLLAMA_TEMPERATURE`: Override temperature (0.0-2.0)

## Usage

### Interactive Mode

Start an interactive session:

```bash
cla
# or
cla --interactive
```

Type your questions and press Enter. Type `quit`, `exit`, or `q` to exit.

### Single Query Mode

Ask a single question:

```bash
cla "How do I install a package?"
```

### Command Execution Mode

Execute commands automatically with intelligent analysis:

```bash
cla --execute "check disk usage"
```

**Features:**

- Shows AI's thinking process
- Executes commands and displays output
- Analyzes results and reacts accordingly:
  - **Success**: Confirms completion or provides insights
  - **Errors**: Analyzes errors and suggests fixes
  - **Follow-up**: Automatically executes additional commands as needed

**Example:**

```bash
$ cla --execute "check disk usage"

💭 Thinking:
To check disk usage, I'll use the 'df -h' command.

→ Executing: df -h

📤 Command Output (stdout):
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        20G   15G  4.5G  77% /

Return code: 0
✓ Command executed successfully
```

**Error handling:**

```bash
$ cla --execute "install test-package"

→ Executing: sudo dnf install -y test-package

⚠️  Command Error Output (stderr):
Error: No package test-package available.

💭 Thinking:
The package wasn't found. Let me search for available packages.

→ Executing: dnf search test-package
```

### Command Line Options

```bash
cla [OPTIONS] [QUERY]

Options:
  -i, --interactive       Start interactive mode
  -x, --execute          Enable command execution mode
  -y, --yes              Auto-confirm command execution
  --sudo, --allow-sudo   Allow sudo commands (disabled by default)
  --max-iterations INT   Maximum iterations (default: 5, -1 for infinite)
  --timeout INT          Command timeout in seconds (default: 30, -1 for infinite)
  --platform-info        Show detected platform information
  -c, --config PATH      Path to configuration file
  -m, --model TEXT       Override model from config
  -t, --temperature FLOAT  Override temperature (0.0-2.0)
  -e, --endpoint TEXT    Override Ollama endpoint
  --version              Show version
  --help                 Show help
```

### Safety Features

**Input Sanitization:**

All user input is sanitized to prevent injection attacks and malicious content:
- Control characters are removed
- Dangerous patterns (script tags, JavaScript, etc.) are blocked
- Input length limits are enforced
- Path traversal attempts are prevented
- Configuration values are validated

**Dangerous commands are blocked:**

- `rm -rf /` and similar destructive commands
- Disk formatting commands
- System modification commands without confirmation

**Sudo commands are disabled by default:**

```bash
# Sudo is automatically stripped
cla --execute "install nginx"
# Executes: dnf install -y nginx (not sudo dnf...)

# Enable sudo when needed
cla --execute --sudo "install nginx"
```

**Confirmation required for:**

- File deletion commands
- Package uninstallation
- System shutdown/reboot
- Process termination

Use `--yes` to auto-confirm (use with caution).

### Platform Detection

The assistant automatically detects your Linux distribution:

```bash
cla --platform-info
```

**Supported platforms:**

- **RHEL family**: RHEL, CentOS, Fedora, Rocky Linux, AlmaLinux (uses `dnf`/`yum`)
- **Debian family**: Debian, Ubuntu, Raspbian (uses `apt`/`apt-get`)
- **Arch family**: Arch Linux, Manjaro (uses `pacman`)
- **SUSE family**: openSUSE, SUSE Linux Enterprise (uses `zypper`)
- **Gentoo**: Gentoo Linux (uses `emerge`)

Commands are automatically adapted to your platform.

### Daemon Service

Run as a background service:

```bash
# Start service
sudo systemctl start command-line-assistant

# Enable on boot
sudo systemctl enable command-line-assistant

# Check status
sudo systemctl status command-line-assistant

# View logs
sudo journalctl -u command-line-assistant -f
```

## Requirements

- **Python**: 3.8 or higher
- **Ollama**: Server running and accessible
- **Dependencies** (installed automatically):
  - `requests >= 2.28.0`
  - `click >= 8.0.0`
  - `tomli >= 2.0.0` (for Python < 3.11)

## Development

### Setup Development Environment

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
make test
# or
pytest
```

### Build Package

```bash
make build
```

### Clean Build Artifacts

```bash
make clean
```

## Architecture

The codebase is organized into logical modules:

- **`cli.py`**: Command-line interface and user interaction
- **`client.py`**: Ollama API client with streaming and structured outputs support
- **`config.py`**: Configuration management with TOML support
- **`executor.py`**: Command execution with safety checks
- **`platform_detector.py`**: Linux distribution detection
- **`prompt_builder.py`**: System prompt generation with self-learning
- **`schemas.py`**: JSON schemas for structured outputs
- **`sanitizer.py`**: Input sanitization and validation
- **`daemon.py`**: Background service implementation
- **`logger.py`**: Centralized logging configuration
- **`exceptions.py`**: Custom exception classes

### Structured Outputs

The assistant uses [Ollama's structured outputs feature](https://ollama.com/blog/structured-outputs) for reliable command extraction. When executing commands, the AI response is constrained to a JSON schema that includes:

- `thinking`: The reasoning behind the action
- `command`: The command to execute (if any)
- `task_complete`: Whether the task is finished

This provides more reliable parsing than regex-based extraction and automatically falls back to the legacy format if structured outputs are unavailable.

## Troubleshooting

### Connection Errors

Verify Ollama is running:

```bash
curl http://localhost:11434/api/tags
```

Check your configuration:

```bash
python3 -c "from command_line_assistant.config import get_config; c = get_config(); print(f'Endpoint: {c.ollama_endpoint}'); print(f'Model: {c.ollama_model}')"
```

### Configuration Issues

Ensure your TOML file is valid:

```bash
python3 -m tomli config.toml
```

### Permission Errors

If you see permission errors, check:

- Config file permissions
- Learning data file location (`~/.config/command-line-assistant/`)
- System service permissions (if using daemon)

## Contributing

Contributions are welcome! Please see `CONTRIBUTING.md` for guidelines.

## License

Apache-2.0

## Links

- **GitHub**: https://github.com/rhel-lightspeed/command-line-assistant
- **Documentation**: https://command-line-assistant.readthedocs.io
