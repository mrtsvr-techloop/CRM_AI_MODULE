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
    """Assistant ID resolution order:

    1) DocType field (AI Assistant Settings.assistant_id) if set
    2) AI_OPENAI_ASSISTANT_ID from environment
    3) persisted file under private/files
    """
    try:
        doc = frappe.get_single("AI Assistant Settings")
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
	"""Return plain-text prompt/instructions from the Doctype only.

	Uses AI Assistant Settings.instructions, strips HTML, returns None if empty.
	"""
	try:
		doc = frappe.get_single("AI Assistant Settings")
		instr_html = doc.instructions or ""
		instr = clean_html(instr_html).strip()
		return instr or None
	except Exception:
		return None


def get_env_assistant_spec() -> Optional[Dict[str, str]]:
    """Return name/model for Assistant strictly from env when both are present.

    Instructions are no longer read from env; the prompt comes from DocType.
    """
    env = get_environment()
    name = env.get("AI_ASSISTANT_NAME")
    model = env.get("AI_ASSISTANT_MODEL")
    if not (name and model):
        return None
    return {"name": name, "model": model}