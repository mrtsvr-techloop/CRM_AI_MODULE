from __future__ import annotations

import os
from typing import Dict, Optional

import frappe
from frappe.utils.html_utils import clean_html

# OpenAI environment keys
OPENAI_API_KEY = "OPENAI_API_KEY"
OPENAI_ORG_ID = "OPENAI_ORG_ID"
OPENAI_PROJECT = "OPENAI_PROJECT"
OPENAI_BASE_URL = "OPENAI_BASE_URL"


def _log():
	"""Get Frappe logger for config module."""
	return frappe.logger("ai_module.config")


def _get_frappe_environment() -> Dict[str, str]:
	"""Get environment variables from Frappe configuration.
	
	Frappe Cloud allows setting environment variables via GUI which are
	stored in frappe.conf.environment. This function extracts them with
	fallback to empty dict if not configured.
	
	Returns:
		Dict of environment variables (normalized to strings)
	"""
	# Try attribute access first (most common)
	env_from_conf = getattr(frappe.conf, "environment", None)
	
	# Fallback to dict-style access for some deployments
	if env_from_conf is None:
		env_from_conf = getattr(frappe.conf, "get", lambda x: None)("environment")
	
	# Normalize to dict with string keys/values
	if isinstance(env_from_conf, dict):
		return {str(k): str(v) for k, v in env_from_conf.items() if v is not None}
	
	return {}


def _get_ai_settings():
	"""Get AI Assistant Settings singleton if available.
	
	Returns None if DocType is not installed or not accessible.
	"""
	try:
		return frappe.get_single("AI Assistant Settings")
	except Exception:
		return None


def _get_decrypted_api_key() -> Optional[str]:
	"""Securely retrieve the decrypted OpenAI API key from settings.
	
	Returns:
		API key string or None if not set/accessible
	"""
	try:
		from frappe.utils.password import get_decrypted_password
		
		api_key = get_decrypted_password(
			"AI Assistant Settings",
			"AI Assistant Settings",
			"api_key",
			raise_exception=False,
		)
		return (api_key or "").strip() or None
	except Exception:
		return None


def _get_settings_overrides() -> Dict[str, str]:
	"""Extract environment overrides from AI Assistant Settings DocType.
	
	Only returns overrides if use_settings_override flag is enabled.
	Includes API key, base URL, org ID, project, assistant name/model.
	
	Returns:
		Dict of environment variable overrides
	"""
	settings = _get_ai_settings()
	if not settings or not getattr(settings, "use_settings_override", 0):
		return {}
	
	overrides: Dict[str, str] = {}
	
	# API key (encrypted field)
	api_key = _get_decrypted_api_key()
	if api_key:
		overrides[OPENAI_API_KEY] = api_key
	
	# Optional provider configuration fields
	field_mapping = {
		OPENAI_BASE_URL: "base_url",
		OPENAI_ORG_ID: "org_id",
		OPENAI_PROJECT: "project",
		"AI_ASSISTANT_NAME": "assistant_name",
		"AI_ASSISTANT_MODEL": "model",
	}
	
	for env_key, field_name in field_mapping.items():
		value = (getattr(settings, field_name, "") or "").strip()
		if value:
			overrides[env_key] = value
	
	return overrides


def get_environment() -> Dict[str, str]:
	"""Get merged environment variables from all sources.
	
	Precedence order (later overrides earlier):
	1. OS environment variables (os.environ)
	2. Frappe Cloud environment (frappe.conf.environment)
	3. AI Assistant Settings DocType (if use_settings_override enabled)
	
	This allows configuration via Frappe Cloud GUI or DocType without
	code changes, with DocType having highest priority for flexibility.
	
	Returns:
		Dict of all environment variables
	"""
	# Start with OS environment
	merged: Dict[str, str] = dict(os.environ)
	
	# Override with Frappe-specific environment
	merged.update(_get_frappe_environment())
	
	# Override with DocType settings (highest priority)
	merged.update(_get_settings_overrides())
	
	return merged


def apply_environment() -> None:
	"""Apply OpenAI environment variables to the process.
	
	Extracts OpenAI-specific keys from merged environment and sets them
	in os.environ so the OpenAI SDK can use them. Only sets keys that
	have non-empty values.
	
	Required keys:
	- OPENAI_API_KEY (required for API access)
	
	Optional keys:
	- OPENAI_ORG_ID (for organization-specific API)
	- OPENAI_PROJECT (for project-specific API)
	- OPENAI_BASE_URL (for custom API endpoints)
	"""
	env = get_environment()
	
	# Apply OpenAI-specific environment variables
	openai_keys = [OPENAI_API_KEY, OPENAI_ORG_ID, OPENAI_PROJECT, OPENAI_BASE_URL]
	
	for key in openai_keys:
		value = env.get(key)
		if value:
			os.environ[key] = value


def get_settings_prompt_only() -> Optional[str]:
	"""Get AI instructions/prompt from DocType settings.
	
	Only returns instructions if use_settings_override flag is enabled,
	otherwise returns None to allow environment variables to take precedence.
	Converts HTML instructions to plain text.
	
	Returns:
		Plain-text instructions or None
	"""
	settings = _get_ai_settings()
	if not settings or not getattr(settings, "use_settings_override", 0):
		return None
	
	# Extract and clean HTML instructions
	instructions_html = getattr(settings, "instructions", "") or ""
	instructions_text = clean_html(instructions_html).strip()
	
	return instructions_text or None


def get_env_assistant_spec() -> Optional[Dict[str, str]]:
	"""Get assistant specification from environment variables.
	
	Only returns environment-based spec when DocType override is disabled.
	When override is enabled, returns None to indicate DocType should be used.
	
	Extracts:
	- AI_ASSISTANT_NAME: Assistant name
	- AI_ASSISTANT_MODEL: Model to use (e.g., gpt-4)
	- AI_INSTRUCTIONS or AI_ASSISTANT_INSTRUCTIONS: Instructions/prompt
	
	Returns:
		Dict with name/model/instructions keys, or None if override enabled
	"""
	# Skip if DocType override is active
	settings = _get_ai_settings()
	if settings and getattr(settings, "use_settings_override", 0):
		return None
	
	# Extract from environment
	env = get_environment()
	name = env.get("AI_ASSISTANT_NAME")
	model = env.get("AI_ASSISTANT_MODEL")
	instructions = (
		env.get("AI_INSTRUCTIONS") or 
		env.get("AI_ASSISTANT_INSTRUCTIONS") or 
		""
	).strip()
	
	# Return spec only if at least one value exists
	if not (name or model or instructions):
		return None
	
	spec: Dict[str, str] = {}
	if name:
		spec["name"] = name
	if model:
		spec["model"] = model
	if instructions:
		spec["instructions"] = instructions
	
	return spec