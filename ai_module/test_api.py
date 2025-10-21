import frappe
import traceback
import os
from typing import Dict, Any, Optional


def run_ai_tests(phone_number: str = "+393926012793") -> Dict[str, Any]:
	"""Run comprehensive AI tests with phone number input.
	
	Args:
		phone_number: Phone number to use for testing
		
	Returns:
		Dict with test results and debug information
	"""
	results = {
		"phone_number": phone_number,
		"timestamp": frappe.utils.now(),
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
		frappe.logger("ai_module.debug").info(f"TEST: {message}")

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

	# Test 1: AI Session Creation
	def test_ai_session_creation():
		"""Test AI session creation with phone number."""
		log_debug("Testing AI session creation...")
		try:
			from .agents.threads import run_with_responses_api
			from .agents.bootstrap import initialize
			
			# Initialize system
			initialize()
			log_debug("AI system initialized successfully")
			
			# Create phone-to-session mapping
			phone_to_session = {phone_number: "test_session_123"}
			log_debug("Phone-to-session mapping created", {"mapping": phone_to_session})
			
			# Test session creation
			result = run_with_responses_api(
				message="ciao",
				session_id="test_session_123",
				timeout_s=30
			)
			log_debug("AI session creation completed", {"result": result})
			
			return {
				"status": "pass",
				"message": "AI session creation successful",
				"result": result
			}
		except Exception as e:
			log_debug("FAILED AI session creation", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"AI session creation failed: {str(e)}",
				"error_details": {
					"error": str(e),
					"type": type(e).__name__,
					"traceback": traceback.format_exc()
				}
			}

	# Test 2: WhatsApp Message Processing
	def test_whatsapp_message_processing():
		"""Test WhatsApp message processing with phone number."""
		log_debug("Testing WhatsApp message processing...")
		test_payload = {
			"from": phone_number,
			"message": "ciao",
			"content_type": "text",
			"timestamp": frappe.utils.now()
		}
		log_debug("Test payload created", {"payload": test_payload})
		try:
			from .integrations.whatsapp import process_incoming_whatsapp_message
			log_debug("WhatsApp processing function imported successfully")
		except Exception as e:
			log_debug("FAILED to import WhatsApp processing function", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "error", "message": f"Failed to import WhatsApp processing: {str(e)}"}
		try:
			log_debug("Attempting to process WhatsApp message...")
			process_incoming_whatsapp_message(test_payload)
			log_debug("WhatsApp message processing completed successfully")
			return {
				"status": "pass",
				"message": "WhatsApp message processing successful",
				"payload": test_payload
			}
		except Exception as e:
			log_debug("FAILED to process WhatsApp message", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"Failed to process WhatsApp message: {str(e)}",
				"error_details": {
					"error": str(e),
					"type": type(e).__name__,
					"traceback": traceback.format_exc()
				}
			}

	# Test 3: AI Agent Execution
	def test_ai_agent_execution():
		"""Test AI agent execution."""
		log_debug("Testing AI agent execution...")
		try:
			from .agents.runner import run_agent
			from .agents.bootstrap import initialize
			
			initialize()
			log_debug("AI system initialized for agent test")
			
			result = run_agent(
				agent_or_name="whatsapp_assistant",
				input_text="ciao",
				session_id="test_session_123"
			)
			log_debug("AI agent execution completed", {"result": result})
			
			return {
				"status": "pass",
				"message": "AI agent execution successful",
				"result": result
			}
		except Exception as e:
			log_debug("FAILED AI agent execution", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"AI agent execution failed: {str(e)}",
				"error_details": {
					"error": str(e),
					"type": type(e).__name__,
					"traceback": traceback.format_exc()
				}
			}

	# Test 4: WhatsApp Autoreply Settings
	def test_whatsapp_autoreply_settings():
		"""Test WhatsApp autoreply settings."""
		log_debug("Testing WhatsApp autoreply settings...")
		try:
			from .integrations.whatsapp import _should_autoreply, _send_autoreply
			log_debug("WhatsApp autoreply functions imported successfully")
		except Exception as e:
			log_debug("FAILED to import autoreply functions", {"error": str(e), "traceback": traceback.format_exc()})
			return {"status": "error", "message": f"Failed to import autoreply functions: {str(e)}"}
		try:
			should_reply = _should_autoreply()
			log_debug("Autoreply check completed", {"should_reply": should_reply})
			return {
				"status": "pass",
				"message": f"Autoreply check completed: {should_reply}",
				"should_autoreply": should_reply
			}
		except Exception as e:
			log_debug("FAILED to check autoreply settings", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"Failed to check autoreply settings: {str(e)}",
				"error_details": {
					"error": str(e),
					"type": type(e).__name__,
					"traceback": traceback.format_exc()
				}
			}

	# Run all tests
	log_debug(f"Starting AI tests with phone number: {phone_number}")
	
	results["tests"]["ai_session_creation"] = safe_test("AI Session Creation", test_ai_session_creation)
	results["tests"]["whatsapp_message_processing"] = safe_test("WhatsApp Message Processing", test_whatsapp_message_processing)
	results["tests"]["ai_agent_execution"] = safe_test("AI Agent Execution", test_ai_agent_execution)
	results["tests"]["whatsapp_autoreply_settings"] = safe_test("WhatsApp Autoreply Settings", test_whatsapp_autoreply_settings)
	
	log_debug("All AI tests completed")
	return results


@frappe.whitelist()
def run_ai_tests_api(phone_number: str = "+393926012793"):
	"""API endpoint to run AI tests."""
	return run_ai_tests(phone_number)
