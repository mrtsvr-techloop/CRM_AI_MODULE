from __future__ import annotations

import os
from typing import Dict, Optional

import frappe
from frappe.utils.html_utils import clean_html


def _get_frappe_environment() -> Dict[str, str]:
	"""Return environment dict from frappe.conf.environment if present.

	This leverages Frappe Cloud's Environment Variables GUI. Falls back to an
	empty dict when not configured.
	"""
	# Some deployments expose as attribute, others via dict key access
	env_from_conf = getattr(frappe.conf, "environment", None)
	if env_from_conf is None:
		try:
			env_from_conf = frappe.conf.get("environment")  # type: ignore[attr-defined]
		except Exception:
			env_from_conf = None
	if isinstance(env_from_conf, dict):
		# Normalize keys to strings
		return {str(k): str(v) for k, v in env_from_conf.items() if v is not None}
	return {}


def get_environment() -> Dict[str, str]:
	"""Merged environment with precedence: frappe.conf.environment -> os.environ.

	We favor Frappe's environment (set via Frappe Cloud UI) so you can configure
	secrets without code changes. Missing keys fall back to process env.
	"""
	merged: Dict[str, str] = {}
	merged.update(os.environ)
	merged.update(_get_frappe_environment())

	# Overlay from DocType when user opted-in to use settings
	try:
		# Import inside function to avoid circular imports at module load
		doc = frappe.get_single("AI Assistant Settings")
		use_settings = bool(getattr(doc, "use_settings", 0))
		if use_settings:
			overrides: Dict[str, str] = {}
			# Securely read password field
			try:
				from frappe.utils.password import get_decrypted_password
				api_key = (
					get_decrypted_password(
						"AI Assistant Settings",
						"AI Assistant Settings",
						"api_key",
						raise_exception=False,
					)
					or ""
				).strip()
				if api_key:
					overrides["OPENAI_API_KEY"] = api_key
			except Exception:
				pass
			# Optional provider configuration
			for key, val in (
				("OPENAI_BASE_URL", getattr(doc, "base_url", "")),
				("OPENAI_ORG_ID", getattr(doc, "org_id", "")),
				("OPENAI_PROJECT", getattr(doc, "project", "")),
				("AI_ASSISTANT_NAME", getattr(doc, "assistant_name", "")),
				("AI_ASSISTANT_MODEL", getattr(doc, "model", "")),
			):
				val_str = (val or "").strip()
				if val_str:
					overrides[key] = val_str
			merged.update(overrides)
	except Exception:
		# Ignore if DocType not installed or not accessible in this context
		pass

	return merged


def apply_environment() -> None:
    """Apply minimal OpenAI environment variables.

    Only sets keys required for OpenAI Threads usage.
    Supported keys:
    - OPENAI_API_KEY (required)
    - OPENAI_ORG_ID (optional)
    - OPENAI_PROJECT (optional)
    """
    env = get_environment()
    for key in (
        "OPENAI_API_KEY",
        "OPENAI_ORG_ID",
        "OPENAI_PROJECT",
    ):
        val = env.get(key)
        if val:
            os.environ[key] = val


 # Removed: local default model handling; Threads uses AI_ASSISTANT_MODEL


 # Removed: session DB path; not used when forcing OpenAI Threads


 # Removed: session mode; we always use OpenAI Threads


def _assistant_id_file_path() -> Optional[str]:
	try:
		return frappe.utils.get_site_path("private", "files", "ai_assistant_id.txt")
	except Exception:
		return None


def set_persisted_assistant_id(assistant_id: str) -> None:
	"""Persist assistant id in private files for later reuse."""
	path = _assistant_id_file_path()
	if not path:
		return
	try:
		# Ensure directory exists
		dirpath = os.path.dirname(path)
		os.makedirs(dirpath, exist_ok=True)
		with open(path, "w", encoding="utf-8") as f:
			f.write(assistant_id.strip())
	except Exception:
		# Best-effort; ignore persistence failures
		pass


def _get_persisted_assistant_id() -> Optional[str]:
	path = _assistant_id_file_path()
	if not path:
		return None
	try:
		if os.path.exists(path):
			with open(path, "r", encoding="utf-8") as f:
				val = f.read().strip()
				return val or None
	except Exception:
		return None
	return None


def get_openai_assistant_id() -> Optional[str]:
	"""Assistant ID resolution with Doctype override flag.

	Order of precedence:
	1) If DocType flag `use_settings_override` is enabled AND assistant_id is set, use it
	2) AI_OPENAI_ASSISTANT_ID from environment
	3) persisted file under private/files
	"""
	try:
		doc = frappe.get_single("AI Assistant Settings")
		if getattr(doc, "use_settings_override", 0):
			dt_val = (getattr(doc, "assistant_id", None) or "").strip()
			if dt_val:
				return dt_val
	except Exception:
		pass
	env_val = get_environment().get("AI_OPENAI_ASSISTANT_ID")
	if env_val:
		return env_val
	return _get_persisted_assistant_id()


def get_settings_prompt_only() -> Optional[str]:
	"""Return plain-text prompt/instructions from the DocType when allowed by flag.

	When `use_settings_override` is disabled, returns None so that env takes precedence.
	"""
	try:
		doc = frappe.get_single("AI Assistant Settings")
		if not getattr(doc, "use_settings_override", 0):
			return None
		instr_html = doc.instructions or ""
		instr = clean_html(instr_html).strip()
		return instr or None
	except Exception:
		return None


def get_env_assistant_spec() -> Optional[Dict[str, str]]:
	"""Return name/model/instructions from env when DocType override is disabled.

	- If DocType flag is ON, we consider only DocType values (env ignored for these).
	- If flag is OFF, use env for name/model and optionally instructions via AI_INSTRUCTIONS.
	"""
	env = get_environment()
	try:
		doc = frappe.get_single("AI Assistant Settings")
		if getattr(doc, "use_settings_override", 0):
			return None
	except Exception:
		pass
	name = env.get("AI_ASSISTANT_NAME")
	model = env.get("AI_ASSISTANT_MODEL")
	instr = (env.get("AI_INSTRUCTIONS") or env.get("AI_ASSISTANT_INSTRUCTIONS") or "").strip()
	if name or model or instr:
		data: Dict[str, str] = {}
		if name:
			data["name"] = name
		if model:
			data["model"] = model
		if instr:
			data["instructions"] = instr
		return data
	return None