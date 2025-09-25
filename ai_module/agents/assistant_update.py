from __future__ import annotations

from typing import Optional

import frappe
from openai import OpenAI

from .assistant_setup import ensure_openai_assistant
from .config import apply_environment, get_env_assistant_spec, get_openai_assistant_id, set_persisted_assistant_id
from .assistant_spec import get_assistant_tools


def get_current_instructions() -> str:
	"""Return instructions from singleton DocType if present, else fallback to code.

	DocType: AI Assistant Settings (field: instructions)
	"""
	try:
		val = frappe.db.get_single_value("AI Assistant Settings", "instructions")
		if val and str(val).strip():
			return str(val)
	except Exception:
		pass
	# Fallback to code-defined prompt
	from .assistant_spec import get_instructions

	return get_instructions()


def get_current_tools():
	"""Return tool schemas from code aggregation."""
	return get_assistant_tools() or None


def upsert_assistant(force: bool = False) -> str:
	"""Ensure an Assistant exists and matches current name/model/instructions/tools.

	- If no assistant exists, create it.
	- If it exists or force is True, update it with current values.
	Returns the assistant id.
	"""
	apply_environment()
	spec_env = get_env_assistant_spec()  # name, model from env
	instructions = get_current_instructions()
	tools = get_current_tools()

	client = OpenAI()
	assistant_id: Optional[str] = get_openai_assistant_id()

	if not assistant_id:
		assistant = client.beta.assistants.create(
			name=spec_env.get("name"),
			instructions=instructions,
			model=spec_env.get("model"),
			tools=tools,
		)
		assistant_id = assistant.id
		set_persisted_assistant_id(assistant_id)
		return assistant_id

	# Update existing
	assistant = client.beta.assistants.update(
		assistant_id,
		name=spec_env.get("name"),
		instructions=instructions,
		model=spec_env.get("model"),
		tools=tools,
	)
	set_persisted_assistant_id(assistant.id)
	return assistant.id 