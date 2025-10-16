"""Assistant configuration management for Responses API.

With the modern Responses API, we no longer create/manage OpenAI Assistant objects.
Instead, configuration (model, instructions, tools) is passed directly to each
responses.create call. This module provides helpers to retrieve current config.
"""

from __future__ import annotations

import frappe

from .config import get_settings_prompt_only, get_env_assistant_spec, get_environment
from .assistant_spec import get_assistant_tools
from .logger_utils import get_resilient_logger


def _log():
	"""Get Frappe logger for assistant_update module."""
	return get_resilient_logger("ai_module.assistant_update")


def get_current_instructions() -> str:
	"""Get AI instructions/prompt from DocType or fallback to code.
	
	Priority:
	1. DocType AI Assistant Settings (if use_settings_override enabled)
	2. Code-defined prompt from assistant_spec
	
	Returns:
		Instruction text for the AI
	"""
	# Try DocType first
	instructions = get_settings_prompt_only()
	if instructions:
		return instructions
	
	# Fallback to code-defined prompt
	from .assistant_spec import get_instructions
	return get_instructions()


def get_current_tools():
	"""Get tool schemas for AI function calling.
	
	Retrieves the list of available tools that the AI can use to perform
	actions like creating contacts, updating records, etc.
	
	Returns:
		List of tool schemas or None if no tools available
	
	Example:
		tools = get_current_tools()
		# Returns: [{"type": "function", "function": {...}}, ...]
	"""
	tools = get_assistant_tools()
	return tools if tools else None


def upsert_assistant(force: bool = False) -> str:
	"""Legacy function for backward compatibility.
	
	With Responses API, we no longer create/update Assistant objects.
	Configuration is passed directly to responses.create on each call.
	
	This function is kept for compatibility with existing UI/API calls
	but now just validates configuration and returns success.
	
	Args:
		force: Ignored (kept for API compatibility)
	
	Returns:
		Success message indicating modern API is in use
	"""
	# Validate that we have an API key configured
	if getattr(frappe.flags, "in_install", False):
		return "Installation mode - skipping validation"
	
	if not get_environment().get("OPENAI_API_KEY"):
		_log().warning("No OpenAI API key configured")
		return "No API key configured"
	
	# Validate instructions exist
	instructions = get_current_instructions()
	if not instructions:
		_log().warning("No instructions configured for AI assistant")
	
	# With Responses API, configuration is applied per-call, not persisted
	return "Using Responses API - configuration applied per request"