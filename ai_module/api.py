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
	
	SECURITY: Requires authenticated user. Contains sensitive system information.
	"""
	# Additional security check - ensure user is not Guest
	if frappe.session.user == "Guest":
		frappe.throw("Authentication required", frappe.PermissionError)
	
	# Security logging - track access to sensitive diagnostics
	frappe.logger("ai_module.security").info(
		f"Diagnostics accessed by user: {frappe.session.user} from IP: {frappe.local.request.environ.get('REMOTE_ADDR', 'unknown')}"
	)
	
	# Optional: Add role-based access control
	# Uncomment if you want to restrict to specific roles
	# if not frappe.has_permission("System Manager"):
	#     frappe.throw("System Manager role required", frappe.PermissionError)
	
	import json
	import os
	import inspect
	import traceback
	
	results = {
		"timestamp": frappe.utils.now(),
		"site": frappe.local.site,
		"user": frappe.session.user,
		"tests": {},
		"debug_log": []
	}
	
	def log_debug(message, data=None):
		"""Add debug message to results."""
		entry = {
			"timestamp": frappe.utils.now(),
			"message": message,
			"data": data
		}
		results["debug_log"].append(entry)
		frappe.logger("ai_module.debug").info(f"DIAGNOSTICS: {message}")
	
	def safe_test(test_name, test_func):
		"""Run a test safely and capture EVERYTHING."""
		log_debug(f"Starting test: {test_name}")
		
		try:
			result = test_func()
			log_debug(f"Test {test_name} completed successfully", result)
			return {
				"status": result.get("status", "pass"),
				"message": result.get("message", f"{test_name} completed"),
				"data": result,
				"error": None
			}
		except Exception as e:
			error_info = {
				"error": str(e),
				"type": type(e).__name__,
				"traceback": traceback.format_exc(),
				"args": e.args if hasattr(e, 'args') else None
			}
			log_debug(f"Test {test_name} FAILED", error_info)
			return {
				"status": "error",
				"message": f"{test_name} failed: {str(e)}",
				"data": None,
				"error": error_info
			}
	
	def test_code_deployed():
		"""Test if code is deployed - CAPTURE EVERYTHING."""
		log_debug("Testing code deployment...")
		
		# Try to import threads module
		try:
			from .agents import threads
			log_debug("Successfully imported threads module", {"module_path": str(threads.__file__) if hasattr(threads, '__file__') else "Unknown"})
		except Exception as e:
			log_debug("FAILED to import threads module", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "fail", "message": f"Failed to import threads: {str(e)}"}
		
		# Check if function exists
		if not hasattr(threads, 'run_with_responses_api'):
			log_debug("run_with_responses_api function NOT FOUND")
			return {"status": "fail", "message": "run_with_responses_api function not found"}
		
		log_debug("run_with_responses_api function found")
		
		# Get source code
		try:
			source = inspect.getsource(threads.run_with_responses_api)
			log_debug("Source code retrieved", {"length": len(source), "preview": source[:200]})
		except Exception as e:
			log_debug("FAILED to get source code", {"error": str(e)})
			return {"status": "fail", "message": f"Failed to get source: {str(e)}"}
		
		# Check for key patterns
		checks = {
			"has_function_call": "FUNCTION_CALL" in source or "function_call" in source,
			"has_iteration_check": "iteration == 1" in source,
			"has_user_role": 'role": "user"' in source or "role: \"user\"" in source,
			"has_responses_api": "responses_api" in source.lower(),
			"has_openai_import": "openai" in source.lower()
		}
		
		log_debug("Code pattern checks", checks)
		
		return {
			"status": "pass" if all(checks.values()) else "fail",
			"message": "Code updated" if all(checks.values()) else "Old code - redeploy needed",
			"details": checks,
			"source_length": len(source),
			"source_preview": source[:500]
		}
	
	def test_api_key():
		"""Test API key - CAPTURE EVERYTHING."""
		log_debug("Testing API key configuration...")
		
		# Apply environment
		try:
			apply_environment()
			log_debug("Environment applied successfully")
		except Exception as e:
			log_debug("FAILED to apply environment", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "error", "message": f"Failed to apply environment: {str(e)}"}
		
		# Get environment
		try:
			env = get_environment()
			log_debug("Environment retrieved", {"keys": list(env.keys()), "key_count": len(env)})
		except Exception as e:
			log_debug("FAILED to get environment", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "error", "message": f"Failed to get environment: {str(e)}"}
		
		# Check API key
		api_key = env.get("OPENAI_API_KEY")
		if api_key:
			log_debug("API key found", {"length": len(api_key), "preview": f"{api_key[:10]}...{api_key[-4:]}"})
		else:
			log_debug("API key NOT FOUND")
		
		return {
			"status": "pass" if api_key else "fail",
			"message": f"Present ({api_key[:10]}...{api_key[-4:]})" if api_key else "Not configured",
			"has_key": bool(api_key),
			"key_length": len(api_key) if api_key else 0,
			"all_env_keys": list(env.keys())
		}
	
	def test_settings():
		"""Test settings - CAPTURE EVERYTHING."""
		log_debug("Testing AI Assistant Settings...")
		
		# Check if doctype exists
		doctype_exists = frappe.db.exists("DocType", "AI Assistant Settings")
		log_debug("DocType check", {"exists": doctype_exists})
		
		if not doctype_exists:
			return {"status": "fail", "message": "AI Assistant Settings doctype not found"}
		
		# Get settings
		try:
			settings = frappe.get_single("AI Assistant Settings")
			log_debug("Settings loaded successfully", {"name": settings.name})
		except Exception as e:
			log_debug("FAILED to load settings", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "error", "message": f"Failed to load settings: {str(e)}"}
		
		# Get all fields
		settings_fields = {}
		for field in settings.meta.fields:
			field_name = field.fieldname
			field_value = getattr(settings, field_name, None)
			settings_fields[field_name] = {
				"value": field_value,
				"type": field.fieldtype,
				"required": field.reqd
			}
		
		log_debug("Settings fields extracted", {"field_count": len(settings_fields)})
		
		return {
			"status": "pass" if settings.wa_enable_autoreply else "warning",
			"message": "AutoReply enabled" if settings.wa_enable_autoreply else "AutoReply DISABLED",
			"autoreply": bool(settings.wa_enable_autoreply),
			"inline": bool(settings.wa_force_inline),
			"cooldown": settings.wa_human_cooldown_seconds,
			"all_fields": settings_fields
		}
	
	def test_session_files():
		"""Test session files - CAPTURE EVERYTHING."""
		log_debug("Testing session files...")
		
		files_dir = frappe.utils.get_site_path("private", "files")
		log_debug("Files directory", {"path": files_dir, "exists": os.path.exists(files_dir)})
		
		if not os.path.exists(files_dir):
			log_debug("Files directory does NOT exist")
			return {"status": "fail", "message": "Files directory does not exist"}
		
		# List all files in directory
		try:
			all_files = os.listdir(files_dir)
			log_debug("Directory contents", {"files": all_files, "count": len(all_files)})
		except Exception as e:
			log_debug("FAILED to list directory", {"error": str(e)})
			all_files = []
		
		session_files = {
			"threads": "ai_whatsapp_threads.json",
			"language": "ai_whatsapp_lang.json", 
			"profile": "ai_whatsapp_profile.json",
			"handoff": "ai_whatsapp_handoff.json",
			"messages": "ai_whatsapp_messages.json"
		}
		
		total_sessions = 0
		file_status = {}
		file_details = {}
		
		for file_type, filename in session_files.items():
			log_debug(f"Checking {file_type} file: {filename}")
			
			filepath = os.path.join(files_dir, filename)
			details = {
				"path": filepath,
				"exists": False,
				"readable": False,
				"writable": False,
				"size": 0,
				"content_preview": "",
				"json_valid": False,
				"count": 0,
				"error": None
			}
			
			if os.path.exists(filepath):
				details["exists"] = True
				details["size"] = os.path.getsize(filepath)
				details["readable"] = os.access(filepath, os.R_OK)
				details["writable"] = os.access(filepath, os.W_OK)
				
				log_debug(f"File {filename} exists", {"size": details["size"], "readable": details["readable"]})
				
				try:
					with open(filepath, "r", encoding="utf-8") as f:
						content = f.read().strip()
					details["content_preview"] = content[:200] + "..." if len(content) > 200 else content
					
					if content:
						data = json.loads(content)
						details["json_valid"] = True
						details["count"] = len(data)
						total_sessions += len(data)
						log_debug(f"File {filename} loaded", {"count": len(data), "preview": content[:100]})
					else:
						log_debug(f"File {filename} is empty")
				except Exception as file_error:
					details["error"] = str(file_error)
					log_debug(f"FAILED to read {filename}", {"error": str(file_error)})
			else:
				log_debug(f"File {filename} does NOT exist")
			
			file_status[file_type] = details["count"]
			file_details[file_type] = details
		
		log_debug("Session files analysis complete", {"total_sessions": total_sessions, "file_details": file_details})
		
		return {
			"status": "pass",
			"sessions": total_sessions,
			"details": file_status,
			"message": f"{total_sessions} total active sessions",
			"file_details": file_details,
			"files_dir": files_dir,
			"directory_contents": all_files
		}
	
	def test_whatsapp_messages():
		"""Test WhatsApp messages - CAPTURE EVERYTHING."""
		log_debug("Testing WhatsApp messages...")
		
		# Check if doctype exists
		doctype_exists = frappe.db.exists("DocType", "WhatsApp Message")
		log_debug("WhatsApp Message doctype check", {"exists": doctype_exists})
		
		if not doctype_exists:
			return {"status": "fail", "message": "WhatsApp Message doctype not found"}
		
		# Query messages
		try:
			yesterday = frappe.utils.add_to_date(frappe.utils.now(), days=-1)
			log_debug("Querying messages", {"since": str(yesterday)})
			
			messages = frappe.get_all(
				"WhatsApp Message",
				filters={"creation": [">", yesterday]},
				fields=["name", "type", "creation", "from_number", "to_number", "message_text"],
				order_by="creation desc",
				limit=20
			)
			
			log_debug("Messages query completed", {"count": len(messages), "messages": messages})
		except Exception as e:
			log_debug("FAILED to query messages", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "error", "message": f"Failed to query messages: {str(e)}"}
		
		incoming = [m for m in messages if m.type == "Incoming"]
		outgoing = [m for m in messages if m.type == "Outgoing"]
		
		log_debug("Message analysis", {"incoming": len(incoming), "outgoing": len(outgoing)})
		
		status = "pass"
		if incoming and not outgoing:
			status = "fail"
			message = "Messages received but NO responses sent"
		elif not incoming:
			status = "warning"
			message = "No recent messages"
		else:
			message = f"{len(incoming)} in, {len(outgoing)} out"
		
		return {
			"status": status,
			"incoming": len(incoming),
			"outgoing": len(outgoing),
			"message": message,
			"raw_messages": messages
		}
	
	def test_recent_errors():
		"""Test recent errors - CAPTURE EVERYTHING."""
		log_debug("Testing recent errors...")
		
		# Check if doctype exists
		doctype_exists = frappe.db.exists("DocType", "Error Log")
		log_debug("Error Log doctype check", {"exists": doctype_exists})
		
		if not doctype_exists:
			return {"status": "fail", "message": "Error Log doctype not found"}
		
		# Query errors
		try:
			errors = frappe.get_all(
				"Error Log",
				filters={
					"method": ["like", "%ai_module%"],
					"creation": [">", frappe.utils.add_to_date(frappe.utils.now(), hours=-2)]
				},
				fields=["name", "method", "creation", "error"],
				order_by="creation desc",
				limit=10
			)
			
			log_debug("Errors query completed", {"count": len(errors)})
		except Exception as e:
			log_debug("FAILED to query errors", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "error", "message": f"Failed to query errors: {str(e)}"}
		
		error_details = []
		for err_info in errors:
			try:
				err = frappe.get_doc("Error Log", err_info.name)
				error_details.append({
					"time": str(err.creation),
					"method": err.method,
					"error": err.error[:500] + "..." if len(err.error) > 500 else err.error,
					"full_error": err.error
				})
				log_debug(f"Error loaded: {err_info.name}", {"method": err.method, "error_preview": err.error[:100]})
			except Exception as detail_error:
				log_debug(f"FAILED to load error details for {err_info.name}", {"error": str(detail_error)})
				error_details.append({
					"time": str(err_info.creation),
					"method": err_info.method,
					"error": "Could not load details",
					"detail_error": str(detail_error)
				})
		
		return {
			"status": "fail" if errors else "pass",
			"count": len(errors),
			"errors": error_details,
			"message": f"{len(errors)} errors in last 2h" if errors else "No recent errors"
		}
	
	def test_ai_initialization():
		"""Test AI initialization - CAPTURE EVERYTHING."""
		log_debug("Testing AI initialization...")
		
		try:
			from .agents.bootstrap import initialize
			log_debug("Bootstrap module imported successfully")
		except Exception as e:
			log_debug("FAILED to import bootstrap", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "error", "message": f"Failed to import bootstrap: {str(e)}"}
		
		try:
			initialize()
			log_debug("Bootstrap initialize() called successfully")
		except Exception as e:
			log_debug("FAILED to call initialize()", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "error", "message": f"Failed to initialize: {str(e)}"}
		
		try:
			from .agents.registry import _TOOL_REGISTRY, _AGENT_REGISTRY
			log_debug("Registry imported successfully", {"tools": len(_TOOL_REGISTRY), "agents": len(_AGENT_REGISTRY)})
		except Exception as e:
			log_debug("FAILED to import registry", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "error", "message": f"Failed to import registry: {str(e)}"}
		
		return {
			"status": "pass",
			"message": f"AI Module initialized with {len(_TOOL_REGISTRY)} tools and {len(_AGENT_REGISTRY)} agents",
			"tool_count": len(_TOOL_REGISTRY),
			"agent_count": len(_AGENT_REGISTRY),
			"tools": list(_TOOL_REGISTRY.keys()),
			"agents": list(_AGENT_REGISTRY.keys())
	}
	
	# Run all tests using the modular functions
	log_debug("Starting diagnostics run...")
	
	results["tests"]["code_deployed"] = safe_test("Code Deployed", test_code_deployed)
	results["tests"]["api_key"] = safe_test("API Key", test_api_key)
	results["tests"]["settings"] = safe_test("Settings", test_settings)
	results["tests"]["session_files"] = safe_test("Session Files", test_session_files)
	results["tests"]["whatsapp_messages"] = safe_test("WhatsApp Messages", test_whatsapp_messages)
	results["tests"]["recent_errors"] = safe_test("Recent Errors", test_recent_errors)
	results["tests"]["ai_initialization"] = safe_test("AI Initialization", test_ai_initialization)
	
	log_debug("All tests completed")
	
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


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_conversation_memory(phone_number: str) -> Dict[str, Any]:
	"""Get conversation memory for a specific phone number.
	
	Args:
		phone_number: The phone number to get conversation history for
	
	Returns:
		Dict with conversation data, thread info, and metadata
	"""
	try:
		if frappe.session.user == "Guest":
			frappe.throw("Authentication required", frappe.PermissionError)
		
		if not phone_number or not phone_number.strip():
			frappe.response["http_status_code"] = 400
			return {"success": False, "error": "Phone number is required"}
		
		phone_number = phone_number.strip()
		
		# Import here to avoid circular imports
		from .agents.threads import _load_json_map, _lookup_phone_from_thread
		
		# Load thread mapping
		thread_map = _load_json_map("ai_whatsapp_threads.json")
		thread_id = thread_map.get(phone_number)
		
		if not thread_id:
			frappe.response["http_status_code"] = 404
			return {
				"success": False, 
				"error": f"No conversation found for phone number: {phone_number}",
				"phone_number": phone_number
			}
		
		# Load response mapping to get conversation history
		response_map = _load_json_map("ai_whatsapp_responses.json")
		
		# Get conversation data
		conversation_data = {
			"phone_number": phone_number,
			"thread_id": thread_id,
			"last_response_id": response_map.get(thread_id),
			"conversation_exists": True
		}
		
		# Try to get additional metadata if available
		try:
			# Load language preference
			lang_map = _load_json_map("ai_whatsapp_lang.json")
			conversation_data["language"] = lang_map.get(phone_number, "Unknown")
			
			# Load profile data
			profile_map = _load_json_map("ai_whatsapp_profile.json")
			conversation_data["profile"] = profile_map.get(phone_number, {})
			
			# Load handoff data
			handoff_map = _load_json_map("ai_whatsapp_handoff.json")
			conversation_data["handoff"] = handoff_map.get(phone_number, {})
			
			# Load message history
			messages_map = _load_json_map("ai_whatsapp_messages.json")
			conversation_data["message_history"] = messages_map.get(phone_number, [])
			
		except Exception as meta_error:
			frappe.logger("ai_module").warning(f"Could not load metadata for {phone_number}: {meta_error}")
		
		frappe.response["http_status_code"] = 200
		return {
			"success": True,
			"conversation": conversation_data,
			"message": f"Found conversation for {phone_number}"
		}
		
	except Exception as e:
		frappe.logger("ai_module").error(f"Failed to get conversation memory for {phone_number}: {str(e)}")
		frappe.response["http_status_code"] = 500
		return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=False, methods=["GET"])
def list_all_conversations() -> Dict[str, Any]:
	"""List all active conversations with their phone numbers and thread IDs.
	
	Returns:
		Dict with list of all active conversations
	"""
	try:
		if frappe.session.user == "Guest":
			frappe.throw("Authentication required", frappe.PermissionError)
		
		# Import here to avoid circular imports
		from .agents.threads import _load_json_map
		
		# Load thread mapping
		thread_map = _load_json_map("ai_whatsapp_threads.json")
		response_map = _load_json_map("ai_whatsapp_responses.json")
		
		conversations = []
		for phone_number, thread_id in thread_map.items():
			conversation_info = {
				"phone_number": phone_number,
				"thread_id": thread_id,
				"last_response_id": response_map.get(thread_id),
				"has_response": bool(response_map.get(thread_id))
			}
			conversations.append(conversation_info)
		
		# Sort by phone number
		conversations.sort(key=lambda x: x["phone_number"])
		
		frappe.response["http_status_code"] = 200
		return {
			"success": True,
			"conversations": conversations,
			"total_count": len(conversations),
			"message": f"Found {len(conversations)} active conversations"
		}
		
	except Exception as e:
		frappe.logger("ai_module").error(f"Failed to list conversations: {str(e)}")
		frappe.response["http_status_code"] = 500
		return {"success": False, "error": str(e)}
@frappe.whitelist(allow_guest=False, methods=["POST"])
def reset_sessions() -> Dict[str, Any]:
	"""Reset AI WhatsApp sessions (Cloud-friendly endpoint).
	
	Clears conversation history by resetting session files.
	Accessible via: /api/method/ai_module.api.reset_sessions
	
	SECURITY: Requires authenticated user. Can destroy conversation data.
	"""
	try:
		# Additional security check - ensure user is not Guest
		if frappe.session.user == "Guest":
			frappe.throw("Authentication required", frappe.PermissionError)
		
		# Security logging - track destructive operations
		frappe.logger("ai_module.security").warning(
			f"Session reset initiated by user: {frappe.session.user} from IP: {frappe.local.request.environ.get('REMOTE_ADDR', 'unknown')}"
		)
		
		# Optional: Add role-based access control for destructive operations
		# Uncomment if you want to restrict to specific roles
		# if not frappe.has_permission("System Manager"):
		#     frappe.throw("System Manager role required for session reset", frappe.PermissionError)
		
		import json
		import os
		
		# Ensure the files directory exists
		files_dir = frappe.utils.get_site_path("private", "files")
		os.makedirs(files_dir, exist_ok=True)
		
		# Use the correct file names from the WhatsApp integration
		files_to_reset = [
			"ai_whatsapp_threads.json",      # phone -> session_id mapping
			"ai_whatsapp_lang.json",         # phone -> language mapping  
			"ai_whatsapp_profile.json",     # phone -> profile mapping
			"ai_whatsapp_handoff.json",     # phone -> last_human_activity mapping
			"ai_whatsapp_messages.json",    # phone -> message history mapping
		]
		
		files_reset = []
		files_errors = []
		
		for filename in files_to_reset:
			filepath = os.path.join(files_dir, filename)
			try:
				# Write empty JSON object to reset the file
				with open(filepath, "w", encoding="utf-8") as f:
					json.dump({}, f)
				files_reset.append(filename)
			except Exception as file_error:
				error_msg = f"Failed to reset {filename}: {str(file_error)}"
				frappe.logger("ai_module").error(error_msg)
				files_errors.append(error_msg)
				# Continue with other files even if one fails
		
		result = {
			"status": "success",
			"message": f"Reset {len(files_reset)} session files",
			"files": files_reset
		}
		
		if files_errors:
			result["warnings"] = files_errors
			result["message"] += f" (with {len(files_errors)} warnings)"
		
		return result
		
	except Exception as e:
		error_msg = f"Session reset failed: {str(e)}"
		frappe.logger("ai_module.security").error(error_msg)
		frappe.throw(error_msg) 