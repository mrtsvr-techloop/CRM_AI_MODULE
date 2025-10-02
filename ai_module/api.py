from __future__ import annotations

from typing import Any, Dict, List, Optional

import frappe

from .agents import Agent, register_agent, register_tool, list_agents, list_tools, run_agent
from .agents.config import apply_environment, get_environment, get_session_mode, get_openai_assistant_id, _assistant_id_file_path


@frappe.whitelist(methods=["GET"])
def ai_debug_env() -> Dict[str, Any]:
	"""Return the effective environment and persistence status used by the AI module.

	Useful on Cloud to verify what the app is actually reading without shell access.
	"""
	apply_environment()
	env = get_environment()
	assistant_id = get_openai_assistant_id()
	assistant_id_file = _assistant_id_file_path()
	thread_map_path = None
	try:
		thread_map_path = frappe.utils.get_site_path("private", "files", "ai_whatsapp_threads.json")
	except Exception:
		thread_map_path = None

	def _exists(path: Optional[str]) -> bool:
		import os  # noqa: WPS433
		return bool(path and os.path.exists(path))

	# Only expose relevant keys; do not echo secrets back
	visible_keys = {
		"AI_AGENT_NAME",
		"AI_SESSION_MODE",
		"AI_OPENAI_ASSISTANT_ID",
		"AI_ASSISTANT_NAME",
		"AI_ASSISTANT_MODEL",
		"AI_AUTOREPLY",
		"OPENAI_BASE_URL",
		"OPENAI_ORG_ID",
		"OPENAI_PROJECT",
	}
	filtered_env = {k: env.get(k) for k in sorted(visible_keys)}

	return {
		"env": filtered_env,
		"session_mode": get_session_mode(),
		"assistant_id": assistant_id,
		"assistant_id_file": assistant_id_file,
		"assistant_id_file_exists": _exists(assistant_id_file),
		"thread_map_path": thread_map_path,
		"thread_map_exists": _exists(thread_map_path),
	}


@frappe.whitelist(methods=["POST"])
def ai_reset_persistence(clear_threads: bool = True) -> Dict[str, Any]:
	"""Delete persisted Assistant id and optional thread map to force re-read of env.

	Note: If AI_OPENAI_ASSISTANT_ID is set in env, it still overrides. Remove it in the
	Cloud Environment panel to allow auto-create with new settings.
	"""
	apply_environment()
	deleted = {"assistant_id_file": False, "thread_map": False}
	import os  # noqa: WPS433

	path = _assistant_id_file_path()
	if path and os.path.exists(path):
		try:
			os.remove(path)
			deleted["assistant_id_file"] = True
		except Exception:
			pass

	if clear_threads:
		try:
			thread_map = frappe.utils.get_site_path("private", "files", "ai_whatsapp_threads.json")
			if os.path.exists(thread_map):
				os.remove(thread_map)
				deleted["thread_map"] = True
		except Exception:
			pass

	return {"success": True, "deleted": deleted}


@frappe.whitelist(methods=["POST"])
def ai_register_tool(dotted_path: str, name: Optional[str] = None) -> str:
	"""Register a tool by dotted import path.

	Example dotted path: "techloop_crm.crm.api.activities.create_activity"
	Returns the registered tool name.
	"""
	module_path, func_name = dotted_path.rsplit(".", 1)
	module = __import__(module_path, fromlist=[func_name])
	func = getattr(module, func_name)
	wrapped = register_tool(func, name=name)
	return name or func.__name__


@frappe.whitelist(methods=["POST"])
def ai_register_assistant_tool_impl(tool_name: str, dotted_path: str) -> str:
	"""Register a Python implementation for an Assistant function tool by dotted path."""
	from .agents.tool_registry import register_tool_impl

	module_path, func_name = dotted_path.rsplit(".", 1)
	module = __import__(module_path, fromlist=[func_name])
	func = getattr(module, func_name)
	register_tool_impl(tool_name, func)
	return tool_name


@frappe.whitelist(methods=["POST"])
def ai_register_agent(name: str, instructions: str, model: Optional[str] = None, tool_names: Optional[List[str]] = None) -> str:
	"""Create and register a basic agent.

	- name: registry key
	- instructions: system prompt for the agent
	- model: optional model override (falls back to env default)
	- tool_names: names previously registered via ai_register_tool
	"""
	from agents import Agent as SDKAgent
	from .agents.config import get_default_model
	from .agents.registry import _TOOL_REGISTRY

	tools = []
	if tool_names:
		for t in tool_names:
			if t not in _TOOL_REGISTRY:
				raise frappe.ValidationError(f"Unknown tool: {t}")
			tools.append(_TOOL_REGISTRY[t])

	agent = SDKAgent(
		name=name,
		instructions=instructions,
		model=model or get_default_model(),
		tools=tools or None,
	)
	register_agent(agent, name=name)
	return name


@frappe.whitelist(methods=["GET"])
def ai_list_agents() -> List[str]:
	return list_agents()


@frappe.whitelist(methods=["GET"])
def ai_list_tools() -> List[str]:
	return list_tools()


@frappe.whitelist(methods=["POST"])
def ai_run_agent(agent_name: str, message: str, session_id: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
	"""Run a registered agent and return its final output and metadata."""
	return run_agent(agent_name, message, session_id=session_id, model=model)


@frappe.whitelist()
def ai_get_instructions() -> str:
	"""Return current instructions (DocType value if present, else code)."""
	from .agents.assistant_update import get_current_instructions

	return get_current_instructions()


@frappe.whitelist(methods=["POST"])
def ai_set_instructions(instructions: str) -> str:
	"""Save instructions into the singleton DocType and return updated Assistant id."""
	# Ensure singleton exists; create if missing
	dt = "AI Assistant Settings"
	if not frappe.db.exists("DocType", dt):
		raise frappe.DoesNotExistError("AI Assistant Settings doctype is not installed")
	# Update value
	frappe.db.set_value(dt, dt, "instructions", instructions)
	frappe.db.commit()
	# Upsert Assistant
	from .agents.assistant_update import upsert_assistant

	return upsert_assistant(force=True)


@frappe.whitelist(methods=["POST"])
def ai_update_assistant() -> str:
	"""Force update the Assistant on OpenAI (without changing instructions)."""
	from .agents.assistant_update import upsert_assistant

	return upsert_assistant(force=True) 