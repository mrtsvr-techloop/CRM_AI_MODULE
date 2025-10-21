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
		"OPENAI_BASE_URL",
		"AI_TOOL_CALL_MODE",
	}

	return {
		"environment": {k: v for k, v in env.items() if k in visible_keys},
		"session_files": {
			"thread_map": {
				"path": thread_map_path,
				"exists": _exists(thread_map_path),
			},
			"response_map": {
				"path": response_map_path,
				"exists": _exists(response_map_path),
			},
		},
		"agents": list_agents(),
		"tools": list_tools(),
	}


@frappe.whitelist(methods=["GET"])
def ai_debug_sessions() -> Dict[str, Any]:
	"""Return current AI session status."""
	try:
		from .agents.threads import _load_json_map
		
		thread_map = _load_json_map("ai_whatsapp_threads.json")
		response_map = _load_json_map("ai_response_map.json")
		
		return {
			"thread_map": thread_map,
			"response_map": response_map,
			"session_count": len(thread_map),
			"response_count": len(response_map),
		}
	except Exception as e:
		return {
			"error": str(e),
			"thread_map": {},
			"response_map": {},
			"session_count": 0,
			"response_count": 0,
		}


@frappe.whitelist(methods=["POST"])
def ai_debug_run_agent(
	agent_name: str,
	input_text: str,
	session_id: Optional[str] = None,
	**kwargs: Any,
) -> Dict[str, Any]:
	"""Run an AI agent for debugging purposes."""
	try:
		result = run_agent(
			agent_or_name=agent_name,
			input_text=input_text,
			session_id=session_id,
			**kwargs,
		)
		return {
			"success": True,
			"result": result,
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e),
			"traceback": frappe.get_traceback(),
		}


@frappe.whitelist(methods=["GET"])
def ai_debug_tools() -> Dict[str, Any]:
	"""Return information about registered AI tools."""
	try:
		tools = list_tools()
		tool_info = {}
		
		for tool_name, tool_func in tools.items():
			tool_info[tool_name] = {
				"name": tool_name,
				"function": tool_func.__name__ if hasattr(tool_func, '__name__') else str(tool_func),
				"module": tool_func.__module__ if hasattr(tool_func, '__module__') else "unknown",
			}
		
		return {
			"success": True,
			"tools": tool_info,
			"tool_count": len(tools),
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e),
			"tools": {},
			"tool_count": 0,
		}


@frappe.whitelist(methods=["GET"])
def ai_debug_agents() -> Dict[str, Any]:
	"""Return information about registered AI agents."""
	try:
		agents = list_agents()
		agent_info = {}
		
		for agent_name, agent_obj in agents.items():
			agent_info[agent_name] = {
				"name": agent_name,
				"type": type(agent_obj).__name__,
				"module": agent_obj.__class__.__module__ if hasattr(agent_obj, '__class__') else "unknown",
			}
		
		return {
			"success": True,
			"agents": agent_info,
			"agent_count": len(agents),
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e),
			"agents": {},
			"agent_count": 0,
		}


@frappe.whitelist(methods=["POST"])
def ai_debug_whatsapp_message(
	phone_number: str,
	message: str,
	content_type: str = "text",
) -> Dict[str, Any]:
	"""Simulate a WhatsApp message for debugging."""
	try:
		from .integrations.whatsapp import process_incoming_whatsapp_message
		
		payload = {
			"from": phone_number,
			"message": message,
			"content_type": content_type,
			"timestamp": frappe.utils.now(),
		}
		
		result = process_incoming_whatsapp_message(payload)
		
		return {
			"success": True,
			"payload": payload,
			"result": result,
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e),
			"traceback": frappe.get_traceback(),
		}


@frappe.whitelist(methods=["GET"])
def ai_debug_settings() -> Dict[str, Any]:
	"""Return AI Assistant Settings for debugging."""
	try:
		settings = frappe.get_single("AI Assistant Settings")
		return {
			"success": True,
			"settings": {
				"assistant_id": settings.assistant_id,
				"model": settings.model,
				"enabled": settings.enabled,
				"name": settings.name,
			},
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e),
			"settings": {},
		}


@frappe.whitelist(methods=["POST"])
def ai_debug_reset_sessions() -> Dict[str, Any]:
	"""Reset AI WhatsApp sessions (Cloud-friendly endpoint)."""
	try:
		from .agents.threads import _save_json_map
		
		# Clear session maps
		_save_json_map("ai_whatsapp_threads.json", {})
		_save_json_map("ai_response_map.json", {})
		
		return {
			"success": True,
			"message": "AI sessions reset successfully",
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e),
			"traceback": frappe.get_traceback(),
		}


@frappe.whitelist()
def run_diagnostics():
	"""Run comprehensive diagnostics to check AI module status."""
	results = {
		"timestamp": frappe.utils.now(),
		"status": "running",
		"checks": {},
		"summary": {
			"total_checks": 0,
			"passed": 0,
			"failed": 0,
			"warnings": 0
		}
	}
	
	def log_check(check_name, status, message, data=None):
		"""Add check result to results."""
		results["checks"][check_name] = {
			"status": status,
			"message": message,
			"data": data,
			"timestamp": frappe.utils.now()
		}
		results["summary"]["total_checks"] += 1
		if status == "pass":
			results["summary"]["passed"] += 1
		elif status == "error":
			results["summary"]["failed"] += 1
		elif status == "warning":
			results["summary"]["warnings"] += 1

	# Check 1: Code Deployment
	try:
		import ai_module
		log_check("code_deployed", "pass", "AI module code is deployed", {
			"version": getattr(ai_module, '__version__', 'unknown'),
			"path": ai_module.__file__
		})
	except Exception as e:
		log_check("code_deployed", "error", f"Code deployment issue: {str(e)}")

	# Check 2: API Key Configuration
	try:
		import os
		api_key = os.getenv('OPENAI_API_KEY')
		if api_key:
			log_check("api_key", "pass", "OpenAI API key is configured", {
				"key_length": len(api_key),
				"key_prefix": api_key[:8] + "..." if len(api_key) > 8 else api_key
			})
		else:
			log_check("api_key", "error", "OpenAI API key not found in environment variables")
	except Exception as e:
		log_check("api_key", "error", f"API key check failed: {str(e)}")

	# Check 3: AI Settings
	try:
		settings = frappe.get_single("AI Assistant Settings")
		log_check("ai_settings", "pass", "AI Assistant Settings found", {
			"assistant_id": settings.assistant_id,
			"model": settings.model,
			"use_settings_override": settings.use_settings_override,
			"wa_enable_autoreply": settings.wa_enable_autoreply,
			"wa_enable_reaction": settings.wa_enable_reaction,
			"api_key_present": settings.api_key_present
		})
	except Exception as e:
		log_check("ai_settings", "error", f"AI Settings issue: {str(e)}")

	# Check 4: Session Files
	try:
		import os
		session_files = []
		thread_files = []
		lang_files = []
		
		# Check for session files
		session_path = frappe.get_site_path("private", "files")
		if os.path.exists(session_path):
			for file in os.listdir(session_path):
				if file.startswith("ai_whatsapp_sessions"):
					session_files.append(file)
				elif file.startswith("ai_whatsapp_threads"):
					thread_files.append(file)
				elif file.startswith("ai_whatsapp_lang"):
					lang_files.append(file)
		
		log_check("session_files", "pass", "Session files check completed", {
			"session_files": session_files,
			"thread_files": thread_files,
			"lang_files": lang_files,
			"total_files": len(session_files) + len(thread_files) + len(lang_files)
		})
	except Exception as e:
		log_check("session_files", "error", f"Session files check failed: {str(e)}")

	# Check 5: WhatsApp Messages
	try:
		# Get available fields dynamically
		doctype_fields = frappe.get_meta("WhatsApp Message").fields
		available_fields = [field.fieldname for field in doctype_fields]
		
		# Build query based on available fields
		fields_to_query = []
		if "from" in available_fields:
			fields_to_query.append("from")
		elif "from_number" in available_fields:
			fields_to_query.append("from_number")
		
		if "message" in available_fields:
			fields_to_query.append("message")
		elif "message_text" in available_fields:
			fields_to_query.append("message_text")
		
		if "type" in available_fields:
			fields_to_query.append("type")
		
		if fields_to_query:
			recent_messages = frappe.get_all(
				"WhatsApp Message",
				fields=fields_to_query,
				filters={"type": "Incoming"},
				order_by="creation desc",
				limit=5
			)
			log_check("whatsapp_messages", "pass", f"Found {len(recent_messages)} recent WhatsApp messages", {
				"messages": recent_messages,
				"available_fields": available_fields
			})
		else:
			log_check("whatsapp_messages", "warning", "No suitable fields found for WhatsApp Message query")
	except Exception as e:
		log_check("whatsapp_messages", "error", f"WhatsApp messages check failed: {str(e)}")

	# Check 6: Recent Errors
	try:
		recent_errors = frappe.get_all(
			"Error Log",
			fields=["name", "error", "method", "creation"],
			filters={"creation": [">=", frappe.utils.add_days(frappe.utils.now(), -1)]},
			order_by="creation desc",
			limit=10
		)
		log_check("recent_errors", "pass", f"Found {len(recent_errors)} recent errors", {
			"errors": recent_errors
		})
	except Exception as e:
		log_check("recent_errors", "error", f"Recent errors check failed: {str(e)}")

	# Check 7: AI Initialization
	try:
		from .agents.bootstrap import initialize
		from .agents.config import get_environment
		from .agents.registry import get_registered_tools, get_registered_agents
		
		# Try to get environment and components
		env = get_environment()
		tools = get_registered_tools()
		agents = get_registered_agents()
		
		log_check("ai_initialization", "pass", "AI system components accessible", {
			"environment_keys": list(env.keys()),
			"registered_tools": list(tools.keys()),
			"registered_agents": list(agents.keys())
		})
	except Exception as e:
		log_check("ai_initialization", "error", f"AI initialization check failed: {str(e)}")

	# Check 8: System Information
	try:
		import platform
		import sys
		import os
		
		system_info = {
			"python_version": sys.version,
			"platform": platform.platform(),
			"frappe_version": frappe.__version__,
			"site": frappe.local.site,
			"environment": os.getenv('AI_TOOL_CALL_MODE', 'not_set')
		}
		
		log_check("system_info", "pass", "System information collected", system_info)
	except Exception as e:
		log_check("system_info", "error", f"System info check failed: {str(e)}")

	# Final status
	if results["summary"]["failed"] > 0:
		results["status"] = "error"
	elif results["summary"]["warnings"] > 0:
		results["status"] = "warning"
	else:
		results["status"] = "success"

	return results


@frappe.whitelist()
def run_ai_tests_api(phone_number: str = "+393926012793"):
	"""API endpoint to run AI tests."""
	from .test_api import run_ai_tests
	return run_ai_tests(phone_number)


@frappe.whitelist()
def get_conversation_memory(phone_number: str):
	"""Get conversation memory for a specific phone number."""
	try:
		from .agents.threads import _load_json_map
		
		# Load thread map
		thread_map = _load_json_map("ai_whatsapp_threads.json")
		
		if phone_number not in thread_map:
			return {
				"success": False,
				"error": f"No conversation found for {phone_number}"
			}
		
		thread_id = thread_map[phone_number]
		
		# Load response map
		response_map = _load_json_map("ai_response_map.json")
		
		# Load language file
		lang_map = _load_json_map("ai_whatsapp_lang.json")
		
		# Build conversation data
		conversation = {
			"phone_number": phone_number,
			"thread_id": thread_id,
			"last_response_id": response_map.get(phone_number),
			"language": lang_map.get(phone_number),
			"profile": {},
			"handoff": {},
			"message_history": []
		}
		
		return {
			"success": True,
			"conversation": conversation
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def list_all_conversations():
	"""List all active conversations."""
	try:
		from .agents.threads import _load_json_map
		
		# Load thread map
		thread_map = _load_json_map("ai_whatsapp_threads.json")
		
		# Load response map
		response_map = _load_json_map("ai_response_map.json")
		
		conversations = []
		for phone_number, thread_id in thread_map.items():
			conversations.append({
				"phone_number": phone_number,
				"thread_id": thread_id,
				"has_response": phone_number in response_map
			})
		
		return {
			"success": True,
			"conversations": conversations
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def reset_sessions():
	"""Reset AI WhatsApp sessions."""
	try:
		from .agents.threads import _save_json_map
		
		# Clear session maps
		_save_json_map("ai_whatsapp_threads.json", {})
		_save_json_map("ai_response_map.json", {})
		_save_json_map("ai_whatsapp_lang.json", {})
		
		return {
			"success": True,
			"message": "AI sessions reset successfully"
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def delete_all_ai_files():
	"""Delete ALL AI files from private/files directory."""
	try:
		import os
		
		# List of AI files to delete
		ai_files = [
			"ai_whatsapp_sessions.json",
			"ai_whatsapp_threads.json", 
			"ai_whatsapp_lang.json",
			"ai_response_map.json",
			"ai_whatsapp_messages.json"
		]
		
		deleted_files = []
		failed_files = []
		
		# Get private files directory
		private_files_path = frappe.get_site_path("private", "files")
		
		for filename in ai_files:
			file_path = os.path.join(private_files_path, filename)
			
			try:
				if os.path.exists(file_path):
					os.remove(file_path)
					deleted_files.append(filename)
					frappe.logger("ai_module.debug").info(f"Deleted AI file: {filename}")
				else:
					frappe.logger("ai_module.debug").info(f"AI file not found: {filename}")
			except Exception as e:
				failed_files.append(f"{filename}: {str(e)}")
				frappe.logger("ai_module.debug").error(f"Failed to delete {filename}: {str(e)}")
		
		return {
			"success": True,
			"message": {
				"deleted_files": deleted_files,
				"failed_files": failed_files,
				"total_deleted": len(deleted_files),
				"total_failed": len(failed_files)
			}
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}