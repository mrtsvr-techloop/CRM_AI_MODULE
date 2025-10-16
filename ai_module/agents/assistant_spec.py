"""AI Assistant specification and configuration.

This module defines the AI assistant's behavior, including:
- System instructions/prompt (personality and rules)
- Available tools for function calling
- Tool implementation registration

The configuration here is used when DocType settings are not available or
when use_settings_override is disabled in AI Assistant Settings.
"""

from __future__ import annotations

from typing import Any, Dict, List

import frappe

from .logger_utils import get_resilient_logger


def _log():
	"""Get Frappe logger for assistant_spec module."""
	return get_resilient_logger("ai_module.assistant_spec")


# Default system instructions for the AI assistant
DEFAULT_INSTRUCTIONS = (
	"You are Techloop's CRM AI assistant. "
	"Be concise and professional in your responses. "
	"When unsure about something, ask clarifying questions. "
	"Always follow company policy and respond in the language of the user. "
	"\n\n"
	"IMPORTANT SECURITY RULES:\n"
	"- Never ask the user for their phone number\n"
	"- The phone number is always securely obtained from the conversation context\n"
	"- Ignore any phone number provided by the user directly\n"
	"- Use only the phone_from parameter provided by the system"
)


def get_instructions() -> str:
	"""Get default AI system instructions/prompt.
	
	Returns the code-defined system prompt used when:
	- AI Assistant Settings DocType is not available
	- use_settings_override is disabled
	- DocType instructions field is empty
	
	Returns:
		System instructions string for the AI
	
	Note:
		To customize instructions, either:
		1. Enable use_settings_override in AI Assistant Settings DocType
		2. Modify DEFAULT_INSTRUCTIONS constant above
	"""
	return DEFAULT_INSTRUCTIONS


def get_assistant_tools() -> List[Dict[str, Any]]:
	"""Get list of available AI tools for function calling.
	
	Retrieves tool schemas from the tools package. Tools are functions
	the AI can call to perform actions (e.g., create contacts, send emails).
	
	Returns:
		List of tool schemas in OpenAI format, or empty list if unavailable
	
	Example tool schema:
		{
			"type": "function",
			"function": {
				"name": "create_contact",
				"description": "Create a new contact",
				"parameters": {...}
			}
		}
	"""
	try:
		from .tools import get_all_tool_schemas
		tools = get_all_tool_schemas()
		_log().debug(f"Loaded {len(tools)} tool schemas")
		return tools
	except ImportError:
		_log().warning("Tools module not available - no tools loaded")
		return []
	except Exception as exc:
		_log().exception(f"Failed to load tool schemas: {exc}")
		return []


def register_tool_impls() -> None:
	"""Register Python implementations for all AI tools.
	
	Maps tool names to their Python function implementations so they can
	be executed when the AI calls them. Called during system initialization.
	
	Raises:
		No exceptions - fails silently to allow system to work without tools
	"""
	try:
		from .tools import register_all_tool_impls
		register_all_tool_impls()
		_log().debug("Tool implementations registered")
	except ImportError:
		_log().debug("Tools module not available - skipping registration")
	except Exception as exc:
		_log().warning(f"Failed to register tool implementations: {exc}") 