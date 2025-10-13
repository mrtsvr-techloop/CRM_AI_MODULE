from __future__ import annotations

from typing import Optional

import frappe
from openai import OpenAI
import openai

from .assistant_setup import ensure_openai_assistant
from .config import apply_environment, get_env_assistant_spec, get_openai_assistant_id, set_persisted_assistant_id, get_settings_prompt_only, get_environment
from .assistant_spec import get_assistant_tools


def get_current_instructions() -> str:
	"""Return instructions from singleton DocType only; if empty, use a safe fallback."""
	instr = get_settings_prompt_only()
	if instr:
		return instr
	# Fallback to code-defined prompt (keeps system usable if settings empty)
	from .assistant_spec import get_instructions
	return get_instructions()


def get_current_tools():
	"""Return tool schemas from code aggregation."""
	return get_assistant_tools() or None


def upsert_assistant(force: bool = False) -> str:
	"""Ensure an Assistant exists and matches current name/model/instructions/tools.

	- Prompt (instructions): from Doctype only (preferred). If empty, fallback to code prompt.
	- Name/Model: optional from environment (Frappe Cloud or process env); if missing, use defaults.
	Returns the assistant id.
	"""
	apply_environment()
	spec_env = get_env_assistant_spec() or {}
	instructions = get_current_instructions()
	tools = get_current_tools()

	# Provide safe defaults if env missing
	name = spec_env.get("name") or frappe.db.get_single_value("AI Assistant Settings", "assistant_name") or "AI Assistant"
	model = spec_env.get("model") or frappe.conf.get("AI_ASSISTANT_MODEL") or "gpt-4o-mini"

	# Do not initialize OpenAI client when running install or when API key is missing
	if getattr(frappe.flags, "in_install", False):
		return get_openai_assistant_id() or ""
	if not get_environment().get("OPENAI_API_KEY"):
		return get_openai_assistant_id() or ""

	client = OpenAI()
	assistant_id: Optional[str] = get_openai_assistant_id()

	if not assistant_id:
		assistant = client.beta.assistants.create(
			name=name,
			instructions=instructions,
			model=model,
			tools=tools,
		)
		assistant_id = assistant.id
		set_persisted_assistant_id(assistant_id)
		return assistant_id

	# Update existing
	try:
		assistant = client.beta.assistants.update(
			assistant_id,
			name=name,
			instructions=instructions,
			model=model,
			tools=tools,
		)
		set_persisted_assistant_id(assistant.id)
		return assistant.id
	except openai.NotFoundError:
		# If stored id is invalid or deleted remotely, create a fresh Assistant
		assistant = client.beta.assistants.create(
			name=name,
			instructions=instructions,
			model=model,
			tools=tools,
		)
		set_persisted_assistant_id(assistant.id)
		return assistant.id