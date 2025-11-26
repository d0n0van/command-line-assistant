"""JSON schemas for structured outputs with Ollama."""

from typing import Dict, Any


def get_strategy_selection_schema() -> Dict[str, Any]:
    """
    Get JSON schema for strategy selection responses.

    This schema defines the structure for AI responses when selecting
    which evaluation strategy to use.

    Returns:
        JSON schema dictionary for structured outputs.

    Example response:
        {
            "selected_strategy": "path_detection",
            "reasoning": "The query contains an explicit path /home/user/project",
            "needs_local_context": true,
            "target_path": "/home/user/project",
            "query_type": "file_operation"
        }
    """
    return {
        "type": "object",
        "properties": {
            "selected_strategy": {
                "type": "string",
                "enum": ["path_detection", "pattern_detection", "keyword_detection", "none"],
                "description": "The strategy to use: 'path_detection' for explicit paths, 'pattern_detection' for question patterns, 'keyword_detection' for project keywords, 'none' if no local context needed"
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of why this strategy was selected"
            },
            "needs_local_context": {
                "type": "boolean",
                "description": "Whether local context (tree, files) is needed"
            },
            "target_path": {
                "type": ["string", "null"],
                "description": "The target path if one was detected, null otherwise"
            },
            "query_type": {
                "type": "string",
                "enum": ["file_operation", "project_info", "general"],
                "description": "Type of query: 'file_operation' for file/path operations, 'project_info' for project information requests, 'general' for other queries"
            }
        },
        "required": ["selected_strategy", "reasoning", "needs_local_context", "query_type"],
        "additionalProperties": False,
    }


def get_command_response_schema() -> Dict[str, Any]:
    """
    Get JSON schema for command execution responses.

    This schema defines the structure for AI responses when executing commands.
    The response includes thinking/reasoning, optional array of commands with descriptions, and task status.

    Returns:
        JSON schema dictionary for structured outputs.

    Example response:
        {
            "thinking": "I need to check disk usage. Here are several options:",
            "commands": [
                {
                    "description": "Show disk usage in human-readable format",
                    "command": "df -h"
                },
                {
                    "description": "Show detailed disk usage for current directory",
                    "command": "du -sh ."
                }
            ],
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
            "commands": {
                "type": "array",
                "description": "Array of command options with descriptions. Empty array if no commands needed. Each command should be a Linux/bash command only.",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Brief description of what this command does"
                        },
                        "command": {
                            "type": "string",
                            "description": "The Linux/bash command to execute (without code block markers, just the command itself)"
                        }
                    },
                    "required": ["description", "command"],
                    "additionalProperties": False
                },
                "minItems": 0
            },
            "task_complete": {
                "type": "boolean",
                "description": "Whether the task is complete and no further actions are needed",
            },
        },
        "required": ["thinking", "commands", "task_complete"],
        "additionalProperties": False,
    }

