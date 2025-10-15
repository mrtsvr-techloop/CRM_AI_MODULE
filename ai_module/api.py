"""AI Module Public API.

Provides whitelisted endpoints for AI agent management and debugging.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import frappe

from .agents import Agent, register_agent, register_tool, list_agents, list_tools, run_agent
from .agents.config import apply_environment, get_environment


@frappe.whitelist(methods=["GET"])
def ai_debug_env() -> Dict[str, Any]:
	"""Return the effective environment and session status used by the AI module.

	Useful on Cloud to verify what the app is actually reading without shell access.
	
	Note: With Responses API, we no longer persist assistant_id.
	"""
	apply_environment()
	env = get_environment()
	
	# Get session map paths
	thread_map_path = None
	response_map_path = None
	
	try:
		thread_map_path = frappe.utils.get_site_path("private", "files", "ai_whatsapp_threads.json")
		response_map_path = frappe.utils.get_site_path("private", "files", "ai_response_map.json")
	except Exception:
		pass

	def _exists(path: Optional[str]) -> bool:
		import os
		return bool(path and os.path.exists(path))

	# Only expose relevant keys; do not echo secrets back
	visible_keys = {
		"AI_AGENT_NAME",
		"AI_ASSISTANT_NAME",
		"AI_ASSISTANT_MODEL",
		"AI_AUTOREPLY",
		"AI_WHATSAPP_INLINE",
		"AI_WHATSAPP_QUEUE",
		"AI_WHATSAPP_TIMEOUT",
		"OPENAI_ORG_ID",
		"OPENAI_PROJECT",
		"OPENAI_BASE_URL",
		"OPENAI_API_KEY",  # only presence is reflected via ***
	}
	filtered_env = {
		k: ("***" if k == "OPENAI_API_KEY" and env.get(k) else env.get(k)) 
		for k in sorted(visible_keys)
	}

	return {
		"env": filtered_env,
		"api_mode": "responses_api",
		"session_mode": "phone_to_session_to_response",
		"thread_map_path": thread_map_path,
		"thread_map_exists": _exists(thread_map_path),
		"response_map_path": response_map_path,
		"response_map_exists": _exists(response_map_path),
	}


@frappe.whitelist(methods=["POST"])
def ai_reset_persistence(clear_threads: bool = True) -> Dict[str, Any]:
	"""Delete persisted session maps (phone->session, session->response).

	Args:
		clear_threads: If True, also clear the thread/session mapping
	
	Returns:
		{"success": bool, "deleted": {...}}
	
	Note: With Responses API, we no longer persist assistant_id.
	"""
	import os
	
	deleted = {
		"thread_map": False,
		"response_map": False,
		"language_map": False,
		"human_activity_map": False,
	}

	if clear_threads:
		try:
			# Clear phone -> session mapping
			thread_map = frappe.utils.get_site_path("private", "files", "ai_whatsapp_threads.json")
			if os.path.exists(thread_map):
				os.remove(thread_map)
				deleted["thread_map"] = True
			
			# Clear session -> response_id mapping
			response_map = frappe.utils.get_site_path("private", "files", "ai_response_map.json")
			if os.path.exists(response_map):
				os.remove(response_map)
				deleted["response_map"] = True
			
			# Clear language detection map
			language_map = frappe.utils.get_site_path("private", "files", "ai_language_map.json")
			if os.path.exists(language_map):
				os.remove(language_map)
				deleted["language_map"] = True
			
			# Clear human activity tracking
			activity_map = frappe.utils.get_site_path("private", "files", "ai_human_activity.json")
			if os.path.exists(activity_map):
				os.remove(activity_map)
				deleted["human_activity_map"] = True
		
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
	"""Return current instructions (DocType value if present, else default).
	
	Returns:
		Current assistant instructions as a string
	"""
	from .agents.assistant_update import get_current_instructions

	return get_current_instructions()


@frappe.whitelist(methods=["POST"])
def ai_set_instructions(instructions: str) -> Dict[str, Any]:
	"""Save instructions into the singleton DocType.
	
	Args:
		instructions: New assistant instructions
	
	Returns:
		{"success": bool, "message": str}
	
	Note: With Responses API, instructions are passed directly to each
	response creation call, not stored in an Assistant object.
	"""
	# Ensure singleton exists
	dt = "AI Assistant Settings"
	if not frappe.db.exists("DocType", dt):
		raise frappe.DoesNotExistError("AI Assistant Settings doctype is not installed")
	
	# Update value only if DocType override is enabled
	doc = frappe.get_single(dt)
	if not getattr(doc, "use_settings_override", 0):
		return {
			"success": False,
			"message": "Settings override is not enabled in AI Assistant Settings"
		}
	
	frappe.db.set_value(dt, dt, "instructions", instructions)
	frappe.db.commit()
	
	# Validate configuration
	from .agents.assistant_update import upsert_assistant
	result = upsert_assistant(force=True)
	
	return {
		"success": True,
		"message": result
	}


@frappe.whitelist(methods=["POST"])
def ai_update_assistant() -> Dict[str, Any]:
	"""Validate current assistant configuration.
	
	Returns:
		{"success": bool, "message": str}
	
	Note: With Responses API, there is no persistent Assistant to update.
	This endpoint validates that configuration is correct.
	"""
	from .agents.assistant_update import upsert_assistant

	result = upsert_assistant(force=True)
	
	return {
		"success": True,
		"message": result
	} 