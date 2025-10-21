import frappe
import os
import traceback
from typing import Dict, Any


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
			"enabled": settings.enabled
		})
	except Exception as e:
		log_check("ai_settings", "error", f"AI Settings issue: {str(e)}")

	# Check 4: Session Files
	try:
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
		from .agents.config import get_assistant_config
		from .agents.registry import get_registered_tools, get_registered_agents
		
		# Try to get config without initializing
		config = get_assistant_config()
		tools = get_registered_tools()
		agents = get_registered_agents()
		
		log_check("ai_initialization", "pass", "AI system components accessible", {
			"config": config,
			"registered_tools": list(tools.keys()),
			"registered_agents": list(agents.keys())
		})
	except Exception as e:
		log_check("ai_initialization", "error", f"AI initialization check failed: {str(e)}")

	# Check 8: System Information
	try:
		import platform
		import sys
		
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
