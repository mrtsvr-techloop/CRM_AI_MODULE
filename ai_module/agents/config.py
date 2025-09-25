from __future__ import annotations

import os
from typing import Dict, Optional

import frappe


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
	"""Apply relevant environment variables for the Agents SDK and providers.

	Sets well-known keys into os.environ so underlying SDKs pick them up.
	Supported keys (set these in Frappe Cloud):
	- OPENAI_API_KEY
	- OPENAI_BASE_URL (optional, for Azure/OpenAI-compatible endpoints)
	- OPENAI_ORG_ID (optional)
	- OPENAI_PROJECT (optional)
	- AI_DEFAULT_MODEL (optional)
	- AI_SESSION_DB (optional, SQLite path for session memory)
	- AI_SESSION_MODE (optional: "local" or "openai_threads")
	- AI_OPENAI_ASSISTANT_ID (required when AI_SESSION_MODE=openai_threads)
	- AI_ASSISTANT_NAME (required to auto-create Assistant)
	- AI_ASSISTANT_INSTRUCTIONS (required to auto-create Assistant)
	- AI_ASSISTANT_MODEL (required to auto-create Assistant)
	"""
	env = get_environment()
	for key in (
		"OPENAI_API_KEY",
		"OPENAI_BASE_URL",
		"OPENAI_ORG_ID",
		"OPENAI_PROJECT",
	):
		val = env.get(key)
		if val:
			os.environ[key] = val


def get_default_model() -> str:
	"""Return default model name, override via AI_DEFAULT_MODEL env.

	Used only for local SDK mode. Threads mode relies on AI_ASSISTANT_MODEL.
	"""
	env = get_environment()
	return env.get("AI_DEFAULT_MODEL", "gpt-4o-mini")


def get_session_db_path() -> Optional[str]:
	"""Return SQLite file path for session memory, or None to disable persistence.

	Priority:
	1) AI_SESSION_DB in env
	2) sites/<site>/private/files/ai_sessions.db (if path is resolvable)
	"""
	env = get_environment()
	if env.get("AI_SESSION_DB"):
		return env["AI_SESSION_DB"]
	try:
		# Ensure we place the DB under the site's private files
		return frappe.utils.get_site_path("private", "files", "ai_sessions.db")
	except Exception:
		return None


def get_session_mode() -> str:
	"""Return session mode: "openai_threads" (default) or "local" for SDK-managed memory."""
	mode = get_environment().get("AI_SESSION_MODE", "openai_threads").strip().lower()
	return mode


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
	"""Assistant ID to use for Assistants Threads mode.

	Resolution order:
	1) AI_OPENAI_ASSISTANT_ID from environment
	2) persisted file under private/files
	"""
	env_val = get_environment().get("AI_OPENAI_ASSISTANT_ID")
	if env_val:
		return env_val
	return _get_persisted_assistant_id()


def get_env_assistant_spec() -> Dict[str, str]:
	"""Return Assistant spec strictly from environment variables.

	Requires all of: AI_ASSISTANT_NAME, AI_ASSISTANT_INSTRUCTIONS, AI_ASSISTANT_MODEL
	"""
	env = get_environment()
	name = env.get("AI_ASSISTANT_NAME")
	instructions = env.get("AI_ASSISTANT_INSTRUCTIONS")
	model = env.get("AI_ASSISTANT_MODEL")
	if not (name and instructions and model):
		raise RuntimeError("AI_ASSISTANT_NAME, AI_ASSISTANT_INSTRUCTIONS, AI_ASSISTANT_MODEL must be set in environment to auto-create Assistant")
	return {"name": name, "instructions": instructions, "model": model} 