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


@frappe.whitelist(allow_guest=False, methods=["GET"])
def run_diagnostics() -> Dict[str, Any]:
	"""Run system diagnostics for Cloud environments without console access.
	
	Returns comprehensive health check of AI Module components.
	Accessible via: /api/method/ai_module.api.run_diagnostics
	"""
	import json
	import os
	import inspect
	
	results = {
		"timestamp": frappe.utils.now(),
		"site": frappe.local.site,
		"tests": {}
	}
	
	# Test 1: Code deployed
	try:
		from .agents import threads
		source = inspect.getsource(threads.run_with_responses_api)
		
		checks = {
			"has_function_call": "FUNCTION_CALL" in source or "function_call" in source,
			"has_iteration_check": "iteration == 1" in source,
			"has_user_role": 'role": "user"' in source or "role: \"user\"" in source
		}
		
		results["tests"]["code_deployed"] = {
			"status": "pass" if all(checks.values()) else "fail",
			"details": checks,
			"message": "Code updated" if all(checks.values()) else "Old code - redeploy needed"
		}
	except Exception as e:
		results["tests"]["code_deployed"] = {
			"status": "error",
			"message": str(e)
		}
	
	# Test 2: API Key
	try:
		apply_environment()
		env = get_environment()
		api_key = env.get("OPENAI_API_KEY")
		
		results["tests"]["api_key"] = {
			"status": "pass" if api_key else "fail",
			"message": f"Present ({api_key[:10]}...{api_key[-4:]})" if api_key else "Not configured",
			"has_key": bool(api_key)
		}
	except Exception as e:
		results["tests"]["api_key"] = {
			"status": "error",
			"message": str(e)
		}
	
	# Test 3: Settings
	try:
		settings = frappe.get_single("AI Assistant Settings")
		results["tests"]["settings"] = {
			"status": "pass" if settings.wa_enable_autoreply else "warning",
			"autoreply": bool(settings.wa_enable_autoreply),
			"inline": bool(settings.wa_force_inline),
			"cooldown": settings.wa_human_cooldown_seconds,
			"message": "AutoReply enabled" if settings.wa_enable_autoreply else "AutoReply DISABLED"
		}
	except Exception as e:
		results["tests"]["settings"] = {
			"status": "error",
			"message": str(e)
		}
	
	# Test 4: Session files
	try:
		site_path = frappe.utils.get_site_path()
		files_dir = os.path.join(site_path, "private", "files")
		
		response_file = os.path.join(files_dir, "ai_whatsapp_responses.json")
		sessions_count = 0
		
		if os.path.exists(response_file):
			with open(response_file, "r") as f:
				content = f.read().strip()
			if content:
				data = json.loads(content)
				sessions_count = len(data)
		
		results["tests"]["session_files"] = {
			"status": "pass",
			"sessions": sessions_count,
			"message": f"{sessions_count} active sessions"
		}
	except Exception as e:
		results["tests"]["session_files"] = {
			"status": "error",
			"message": str(e)
		}
	
	# Test 5: Recent messages
	try:
		yesterday = frappe.utils.add_to_date(frappe.utils.now(), days=-1)
		messages = frappe.get_all(
			"WhatsApp Message",
			filters={"creation": [">", yesterday]},
			fields=["name", "type", "creation"],
			order_by="creation desc",
			limit=20
		)
		
		incoming = [m for m in messages if m.type == "Incoming"]
		outgoing = [m for m in messages if m.type == "Outgoing"]
		
		status = "pass"
		if incoming and not outgoing:
			status = "fail"
			message = "Messages received but NO responses sent"
		elif not incoming:
			status = "warning"
			message = "No recent messages"
		else:
			message = f"{len(incoming)} in, {len(outgoing)} out"
		
		results["tests"]["whatsapp_messages"] = {
			"status": status,
			"incoming": len(incoming),
			"outgoing": len(outgoing),
			"message": message
		}
	except Exception as e:
		results["tests"]["whatsapp_messages"] = {
			"status": "error",
			"message": str(e)
		}
	
	# Test 6: Recent errors
	try:
		errors = frappe.get_all(
			"Error Log",
			filters={
				"method": ["like", "%ai_module%"],
				"creation": [">", frappe.utils.add_to_date(frappe.utils.now(), hours=-2)]
			},
			fields=["name", "method", "creation"],
			order_by="creation desc",
			limit=3
		)
		
		error_details = []
		for err_info in errors:
			err = frappe.get_doc("Error Log", err_info.name)
			lines = err.error.split('\n')
			error_type = "Unknown"
			for line in reversed(lines[-10:]):
				if 'Error' in line:
					error_type = line.strip()[:100]
					break
			
			error_details.append({
				"time": str(err.creation),
				"method": err.method,
				"error": error_type
			})
		
		results["tests"]["recent_errors"] = {
			"status": "fail" if errors else "pass",
			"count": len(errors),
			"errors": error_details,
			"message": f"{len(errors)} errors in last 2h" if errors else "No recent errors"
		}
	except Exception as e:
		results["tests"]["recent_errors"] = {
			"status": "error",
			"message": str(e)
		}
	
	# Overall status
	test_statuses = [t.get("status") for t in results["tests"].values()]
	if "fail" in test_statuses or "error" in test_statuses:
		results["overall_status"] = "fail"
		results["overall_message"] = "Issues found - see details"
	elif "warning" in test_statuses:
		results["overall_status"] = "warning"
		results["overall_message"] = "System OK with warnings"
	else:
		results["overall_status"] = "pass"
		results["overall_message"] = "All systems operational"
	
	return results


@frappe.whitelist(allow_guest=False, methods=["POST"])
def reset_sessions() -> Dict[str, Any]:
	"""Reset AI WhatsApp sessions (Cloud-friendly endpoint).
	
	Clears conversation history by resetting session files.
	Accessible via: /api/method/ai_module.api.reset_sessions
	"""
	import json
	import os
	
	try:
		site_path = frappe.utils.get_site_path()
		files_dir = os.path.join(site_path, "private", "files")
		
		files_reset = []
		for filename in ["ai_whatsapp_responses.json", "ai_whatsapp_threads.json", "ai_whatsapp_handoffjson"]:
			filepath = os.path.join(files_dir, filename)
			if os.path.exists(filepath):
				with open(filepath, "w") as f:
					json.dump({}, f)
				files_reset.append(filename)
		
		return {
			"status": "success",
			"message": f"Reset {len(files_reset)} session files",
			"files": files_reset
		}
	except Exception as e:
		frappe.throw(str(e)) 