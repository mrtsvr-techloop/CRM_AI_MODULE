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
from .assistant_spec import get_instructions, get_assistant_tools


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
	spec_env = get_env_assistant_spec()  # requires name + model from env
	instructions = get_instructions()
	tools = get_assistant_tools() or None
	assistant = client.beta.assistants.create(
		name=spec_env.get("name"),
		instructions=instructions,
		model=spec_env.get("model"),
		tools=tools,
	)
	set_persisted_assistant_id(assistant.id)
	frappe.logger().info(f"[ai_module] Created OpenAI Assistant: {assistant.id} ({spec_env.get('name')})")
	return assistant.id 