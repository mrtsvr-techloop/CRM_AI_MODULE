from __future__ import annotations

from typing import Optional

import frappe
from openai import OpenAI

from .config import (
	apply_environment,
	get_openai_assistant_id,
	set_persisted_assistant_id,
	get_env_assistant_spec,
	get_environment,
)
from .assistant_update import get_current_instructions
from .assistant_spec import get_assistant_tools


def ensure_openai_assistant() -> Optional[str]:
	"""Create an OpenAI Assistant using env name/model + code instructions/tools if not configured.

	Called from install hooks and at first use. Returns the assistant id if created/found.
	"""
	apply_environment()
	assistant_id = get_openai_assistant_id()
	if assistant_id:
		return assistant_id

	# Skip creating assistant when no API key is configured or during install
	if getattr(frappe.flags, "in_install", False):
		return None
	if not get_environment().get("OPENAI_API_KEY"):
		return None

	client = OpenAI()
	# Determine source of name/model based on override flag
	name = None
	model = None
	try:
		doc = frappe.get_single("AI Assistant Settings")
		if getattr(doc, "use_settings_override", 0):
			name = (getattr(doc, "assistant_name", None) or "").strip() or None
			model = (getattr(doc, "model", None) or "").strip() or None
		spec_env = get_env_assistant_spec() or {}
		name = name or spec_env.get("name") or frappe.conf.get("AI_ASSISTANT_NAME") or "AI Assistant"
		model = model or spec_env.get("model") or frappe.conf.get("AI_ASSISTANT_MODEL") or "gpt-4o-mini"
	except Exception:
		# Fallback if DocType not available
		spec_env = get_env_assistant_spec() or {}
		name = spec_env.get("name") or frappe.conf.get("AI_ASSISTANT_NAME") or "AI Assistant"
		model = spec_env.get("model") or frappe.conf.get("AI_ASSISTANT_MODEL") or "gpt-4o-mini"

	instructions = get_current_instructions()
	tools = get_assistant_tools() or None
	assistant = client.beta.assistants.create(
		name=name,
		instructions=instructions,
		model=model,
		tools=tools,
	)
	set_persisted_assistant_id(assistant.id)
	frappe.logger().info(f"[ai_module] Created OpenAI Assistant: {assistant.id} ({spec_env.get('name')})")
	return assistant.id 