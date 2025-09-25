from __future__ import annotations

from typing import Any, Dict, List

# Define the Assistant's behavior in code here.
# - get_instructions(): REQUIRED system prompt string
# - get_assistant_tools(): OPTIONAL list of Assistants API tool schemas (function tools)


def get_instructions() -> str:
	"""Return the Assistant's system prompt (instructions)."""
	# TODO: Replace with your production prompt
	return (
		"You are Techloop's CRM AI. Be concise. When unsure, ask clarifying questions. "
		"Follow company policy and respond in the language of the user."
	)


def get_assistant_tools() -> List[Dict[str, Any]]:
	"""Aggregate function tools from the tools package."""
	try:
		from .tools import get_all_tool_schemas
		return get_all_tool_schemas()
	except Exception:
		return []


def register_tool_impls() -> None:
	"""Register Python implementations for all known tools (best-effort)."""
	try:
		from .tools import register_all_tool_impls
		register_all_tool_impls()
	except Exception:
		pass 