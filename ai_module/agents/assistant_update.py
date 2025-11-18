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
	"""Get AI instructions/prompt from DocType, environment, or fallback to code.
	
	Priority:
	1. DocType AI Assistant Settings (if use_settings_override enabled)
	2. Environment variables AI_INSTRUCTIONS or AI_ASSISTANT_INSTRUCTIONS (if exist)
	3. Code-defined prompt from assistant_spec
	
	Replaces {{Cliente}} placeholder with client_name from settings if available.
	
	Returns:
		Instruction text for the AI with placeholders replaced
	"""
	# Get client name from settings
	client_name = _get_client_name()
	
	# Try DocType first
	instructions = get_settings_prompt_only()
	if instructions:
		return _replace_placeholders(instructions, client_name)
	
	# Try environment variables if they exist
	env_spec = get_env_assistant_spec()
	if env_spec and env_spec.get("instructions"):
		return _replace_placeholders(env_spec["instructions"], client_name)
	
	# Fallback to code-defined prompt
	from .assistant_spec import get_instructions
	instructions = get_instructions()
	return _replace_placeholders(instructions, client_name)


def _get_client_name() -> str:
	"""Get client name from AI Assistant Settings.
	
	Returns:
		Client name from settings, or 'il cliente' as default
	"""
	try:
		settings = frappe.get_single("AI Assistant Settings")
		client_name = getattr(settings, "client_name", "") or ""
		return client_name.strip() if client_name else "il cliente"
	except Exception:
		return "il cliente"


def _replace_placeholders(instructions: str, client_name: str) -> str:
	"""Replace placeholders in instructions with actual values.
	
	Args:
		instructions: Instruction text with placeholders
		client_name: Client name to replace {{Cliente}} placeholder
		
	Returns:
		Instructions with placeholders replaced
	"""
	if not instructions:
		return instructions
	
	# Replace {{Cliente}} with actual client name
	instructions = instructions.replace("{{Cliente}}", client_name)
	
	return instructions


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