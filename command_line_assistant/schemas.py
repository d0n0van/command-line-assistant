"""JSON schemas for structured outputs with Ollama."""

from typing import Dict, Any


def get_command_response_schema() -> Dict[str, Any]:
    """
    Get JSON schema for command execution responses.

    This schema defines the structure for AI responses when executing commands.
    The response includes thinking/reasoning, optional command, and task status.

    Returns:
        JSON schema dictionary for structured outputs.

    Example response:
        {
            "thinking": "I need to check disk usage using df -h",
            "command": "df -h",
            "task_complete": false
        }
    """
    return {
        "type": "object",
        "properties": {
            "thinking": {
                "type": "string",
                "description": "The reasoning or explanation for the action taken",
            },
            "command": {
                "type": ["string", "null"],
                "description": "The command to execute in bash code block format (```bash ... ```) or null if no command needed",
            },
            "task_complete": {
                "type": "boolean",
                "description": "Whether the task is complete and no further actions are needed",
            },
        },
        "required": ["thinking", "task_complete"],
        "additionalProperties": False,
    }

