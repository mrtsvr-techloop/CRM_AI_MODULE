import frappe
import traceback
import time
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

	# Test 5: Direct AI Execution
	def test_ai_direct_execution():
		"""Test direct AI execution to see if it can respond to a message."""
		log_debug("Testing direct AI execution...")
		
		try:
			from .agents.runner import run_agent
			from .agents.threads import _save_json_map
			
			# Create a test session
			phone_number = "+393926012793"
			session_id = f"test_session_{int(time.time())}"
			
			# Save session mapping
			_save_json_map("ai_whatsapp_threads.json", {phone_number: session_id})
			
			# Try to run the agent directly
			log_debug("Running AI agent directly...")
			
			result = run_agent(
				agent_or_name="crm_assistant",  # Use the configured agent name
				input_text="ciao - test direct execution",
				session_id=session_id
			)
			
			log_debug("AI execution result", {
				"success": "response" in result or "final_output" in result,
				"response_length": len(result.get("response", result.get("final_output", ""))),
				"response_preview": (result.get("response", result.get("final_output", "")))[:100] if result.get("response") or result.get("final_output") else None,
				"metadata": result
			})
			
			# Check if we got a response (either "response" or "final_output")
			has_response = bool((result.get("response", "") or result.get("final_output", "")).strip())
				
			if has_response:
				response_text = result.get("response", result.get("final_output", ""))
				return {
					"status": "pass",
					"message": f"AI responded successfully! Response: {response_text[:100]}...",
					"response": response_text,
					"metadata": result
				}
			else:
				return {
					"status": "error",
					"message": "AI execution completed but no response generated",
					"result": result
				}
				
		except Exception as e:
			log_debug("FAILED direct AI execution", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"Direct AI execution failed: {str(e)}",
				"error_details": {
					"error": str(e),
					"type": type(e).__name__,
					"traceback": traceback.format_exc()
				}
			}

	# Test 7: WhatsApp Settings Check
	def test_whatsapp_settings():
		"""Test WhatsApp settings to see why AI doesn't respond."""
		log_debug("Testing WhatsApp settings...")
		
		try:
			from .integrations.whatsapp import _should_process_inline, _should_autoreply, _get_ai_settings
			from .agents.config import get_environment
			
			# Check inline processing
			should_inline = _should_process_inline()
			log_debug("Inline processing check", {"should_process_inline": should_inline})
			
			# Check autoreply
			should_autoreply = _should_autoreply()
			log_debug("Autoreply check", {"should_autoreply": should_autoreply})
			
			# Check AI settings
			settings = _get_ai_settings()
			log_debug("AI Settings", {
				"settings_exists": settings is not None,
				"use_settings_override": getattr(settings, "use_settings_override", None) if settings else None,
				"wa_force_inline": getattr(settings, "wa_force_inline", None) if settings else None,
				"wa_enable_autoreply": getattr(settings, "wa_enable_autoreply", None) if settings else None
			})
			
			# Check environment
			env = get_environment()
			log_debug("Environment variables", {
				"AI_WHATSAPP_INLINE": env.get("AI_WHATSAPP_INLINE"),
				"AI_AUTOREPLY": env.get("AI_AUTOREPLY"),
				"AI_AGENT_NAME": env.get("AI_AGENT_NAME")
			})
			
			# Determine status
			if should_inline and should_autoreply:
				status = "pass"
				message = "All WhatsApp settings are correct"
			elif not should_inline:
				status = "warning"
				message = "Inline processing is disabled - messages will be queued"
			elif not should_autoreply:
				status = "warning"
				message = "Autoreply is disabled - AI won't send responses"
			else:
				status = "error"
				message = "Multiple settings issues detected"
			
			return {
				"status": status,
				"message": message,
				"settings": {
					"should_process_inline": should_inline,
					"should_autoreply": should_autoreply,
					"ai_settings": {
						"exists": settings is not None,
						"use_settings_override": getattr(settings, "use_settings_override", None) if settings else None,
						"wa_force_inline": getattr(settings, "wa_force_inline", None) if settings else None,
						"wa_enable_autoreply": getattr(settings, "wa_enable_autoreply", None) if settings else None
					},
					"environment": {
						"AI_WHATSAPP_INLINE": env.get("AI_WHATSAPP_INLINE"),
						"AI_AUTOREPLY": env.get("AI_AUTOREPLY"),
						"AI_AGENT_NAME": env.get("AI_AGENT_NAME")
					}
				}
			}
			
		except Exception as e:
			log_debug("FAILED WhatsApp settings test", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"WhatsApp settings test failed: {str(e)}",
				"error_details": {
					"error": str(e),
					"type": type(e).__name__,
					"traceback": traceback.format_exc()
				}
			}

	# Test 8: Queue Processing Test
	def test_queue_processing():
		"""Test if queue processing works or if we need inline processing."""
		log_debug("Testing queue processing...")
		
		try:
			from .integrations.whatsapp import _enqueue_or_process, _get_queue_config
			import frappe
			
			# Check queue configuration
			queue_name, timeout = _get_queue_config()
			log_debug("Queue config", {"queue_name": queue_name, "timeout": timeout})
			
			# Test payload
			test_payload = {
				"name": "test_queue_message",
				"type": "Incoming",
				"from": "+393926012793",
				"message": "test queue processing",
				"content_type": "text"
			}
			
			# Try to enqueue a test job
			log_debug("Attempting to enqueue test job...")
			
			try:
				frappe.enqueue(
					"ai_module.integrations.whatsapp.process_incoming_whatsapp_message",
					queue=queue_name,
					job_id="test_queue_job",
					payload=test_payload,
					now=False,
					timeout=timeout,
					enqueue_after_commit=True,
				)
				
				log_debug("Job enqueued successfully")
				
				# Check if job exists in queue
				import time
				time.sleep(1)  # Wait a moment
				
				# Try to get job status (this might not work depending on Frappe version)
				try:
					job = frappe.get_doc("Scheduled Job Log", {"job_id": "test_queue_job"})
					job_status = job.status
				except:
					job_status = "unknown"
				
				return {
					"status": "pass",
					"message": "Queue processing appears to work",
					"queue_info": {
						"queue_name": queue_name,
						"timeout": timeout,
						"job_enqueued": True,
						"job_status": job_status
					}
				}
				
			except Exception as e:
				log_debug("Queue enqueue failed", {"error": str(e)})
				return {
					"status": "warning",
					"message": f"Queue processing failed: {str(e)}",
					"recommendation": "Enable inline processing for development",
					"queue_info": {
						"queue_name": queue_name,
						"timeout": timeout,
						"job_enqueued": False,
						"error": str(e)
					}
				}
			
		except Exception as e:
			log_debug("FAILED queue processing test", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"Queue processing test failed: {str(e)}",
				"error_details": {
					"error": str(e),
					"type": type(e).__name__,
					"traceback": traceback.format_exc()
				}
			}

	# Test 9: Fix WhatsApp Settings
	def test_fix_whatsapp_settings():
		"""Fix WhatsApp settings to enable inline processing."""
		log_debug("Fixing WhatsApp settings...")
		
		try:
			from .integrations.whatsapp import _get_ai_settings
			
			# Get current settings
			settings = _get_ai_settings()
			if not settings:
				return {
					"status": "error",
					"message": "AI Settings not found"
				}
			
			log_debug("Current settings", {
				"use_settings_override": getattr(settings, "use_settings_override", None),
				"wa_force_inline": getattr(settings, "wa_force_inline", None),
				"wa_enable_autoreply": getattr(settings, "wa_enable_autoreply", None)
			})
			
			# Update settings to enable inline processing
			settings.use_settings_override = 1
			settings.wa_force_inline = 1  # Enable inline processing
			settings.wa_enable_autoreply = 1  # Ensure autoreply is enabled
			settings.save()
			
			log_debug("Settings updated successfully")
			
			# Verify the change
			from .integrations.whatsapp import _should_process_inline, _should_autoreply
			should_inline = _should_process_inline()
			should_autoreply = _should_autoreply()
			
			return {
				"status": "pass",
				"message": "WhatsApp settings fixed successfully",
				"settings": {
					"use_settings_override": settings.use_settings_override,
					"wa_force_inline": settings.wa_force_inline,
					"wa_enable_autoreply": settings.wa_enable_autoreply,
					"should_process_inline": should_inline,
					"should_autoreply": should_autoreply
				}
			}
			
		except Exception as e:
			log_debug("FAILED to fix WhatsApp settings", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"Failed to fix WhatsApp settings: {str(e)}",
				"error_details": {
					"error": str(e),
					"type": type(e).__name__,
					"traceback": traceback.format_exc()
				}
			}

	# Test 11: Real WhatsApp Message Test
	def test_real_whatsapp_message():
		"""Test with a real WhatsApp message to see if hook is triggered."""
		log_debug("Testing real WhatsApp message...")
		
		try:
			# Create a WhatsApp message that simulates a real incoming message
			import time
			whatsapp_doc = frappe.get_doc({
				"doctype": "WhatsApp Message",
				"type": "Incoming",
				"from": phone_number,
				"message": "ciao - messaggio reale da WhatsApp",
				"content_type": "text",
				"status": "Sent",
				"message_id": f"real_msg_{int(time.time())}",  # Simulate real message ID
				"conversation_id": f"conv_{int(time.time())}"   # Simulate real conversation ID
			})
			
			# Save the document - this should trigger the hook
			whatsapp_doc.insert()
			log_debug("Real WhatsApp Message created", {
				"doc_name": whatsapp_doc.name,
				"type": whatsapp_doc.type,
				"from_field": getattr(whatsapp_doc, 'from', None),
				"message": whatsapp_doc.message,
				"message_id": whatsapp_doc.message_id,
				"conversation_id": whatsapp_doc.conversation_id
			})
			
			# Wait a moment for processing
			time.sleep(3)
			
			# Check if AI responded
			outgoing_messages = frappe.get_all(
				"WhatsApp Message",
				filters={
					"type": "Outgoing",
					"to": phone_number,
					"creation": [">=", whatsapp_doc.creation]
				},
				fields=["name", "message", "creation"],
				order_by="creation desc",
				limit=5
			)
			
			log_debug("Outgoing messages after real WhatsApp message", {
				"count": len(outgoing_messages),
				"messages": outgoing_messages
			})
			
			# Check for any errors
			recent_errors = frappe.get_all(
				"Error Log",
				filters={
					"creation": [">=", whatsapp_doc.creation],
					"method": ["like", "%whatsapp%"]
				},
				fields=["name", "error", "method", "creation"],
				order_by="creation desc",
				limit=5
			)
			
			log_debug("Recent errors after real WhatsApp message", {
				"count": len(recent_errors),
				"errors": recent_errors
			})
			
			# Determine result
			ai_responded = len(outgoing_messages) > 0
			
			if ai_responded:
				return {
					"status": "pass",
					"message": f"SUCCESS: AI responded to real WhatsApp message! Found {len(outgoing_messages)} outgoing messages",
					"whatsapp_doc": {
						"name": whatsapp_doc.name,
						"type": whatsapp_doc.type,
						"from_field": getattr(whatsapp_doc, 'from', None),
						"message": whatsapp_doc.message,
						"message_id": whatsapp_doc.message_id,
						"conversation_id": whatsapp_doc.conversation_id
					},
					"ai_response": {
						"responded": ai_responded,
						"outgoing_messages": outgoing_messages
					},
					"errors": recent_errors
				}
			else:
				return {
					"status": "warning",
					"message": "AI did not respond to real WhatsApp message",
					"whatsapp_doc": {
						"name": whatsapp_doc.name,
						"type": whatsapp_doc.type,
						"from_field": getattr(whatsapp_doc, 'from', None),
						"message": whatsapp_doc.message,
						"message_id": whatsapp_doc.message_id,
						"conversation_id": whatsapp_doc.conversation_id
					},
					"ai_response": {
						"responded": ai_responded,
						"outgoing_messages": outgoing_messages
					},
					"errors": recent_errors,
					"debug_info": "Check logs for hook execution details"
				}
			
		except Exception as e:
			log_debug("FAILED real WhatsApp message test", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"Real WhatsApp message test failed: {str(e)}",
				"error_details": {
					"error": str(e),
					"type": type(e).__name__,
					"traceback": traceback.format_exc()
				}
			}

	# Test 12: Check Existing WhatsApp Messages
	def test_existing_whatsapp_messages():
		"""Check if existing WhatsApp messages trigger the AI hook."""
		log_debug("Checking existing WhatsApp messages...")
		
		try:
			# Get recent incoming messages
			recent_messages = frappe.get_all(
				"WhatsApp Message",
				filters={
					"type": "Incoming",
					"creation": [">=", "2025-10-21 15:00:00"]  # Last hour
				},
				fields=["name", "from", "message", "creation", "status"],
				order_by="creation desc",
				limit=10
			)
			
			log_debug("Recent incoming messages", {
				"count": len(recent_messages),
				"messages": recent_messages
			})
			
			# Check if any of these messages have outgoing responses
			messages_with_responses = []
			messages_without_responses = []
			
			for msg in recent_messages:
				# Check for outgoing messages after this incoming message
				outgoing_messages = frappe.get_all(
					"WhatsApp Message",
					filters={
						"type": "Outgoing",
						"to": getattr(msg, 'from', None),
						"creation": [">=", msg.creation]
					},
					fields=["name", "message", "creation"],
					limit=1
				)
				
				if outgoing_messages:
					messages_with_responses.append({
						"incoming": msg,
						"outgoing": outgoing_messages[0]
					})
				else:
					messages_without_responses.append(msg)
			
			log_debug("Message analysis", {
				"with_responses": len(messages_with_responses),
				"without_responses": len(messages_without_responses),
				"messages_with_responses": messages_with_responses,
				"messages_without_responses": messages_without_responses
			})
			
			# Determine result
			if messages_with_responses:
				return {
					"status": "pass",
					"message": f"Found {len(messages_with_responses)} messages with AI responses",
					"analysis": {
						"total_messages": len(recent_messages),
						"with_responses": len(messages_with_responses),
						"without_responses": len(messages_without_responses),
						"response_rate": f"{len(messages_with_responses)/len(recent_messages)*100:.1f}%" if recent_messages else "0%"
					},
					"messages_with_responses": messages_with_responses,
					"messages_without_responses": messages_without_responses
				}
			else:
				return {
					"status": "warning",
					"message": f"Found {len(recent_messages)} messages but none have AI responses",
					"analysis": {
						"total_messages": len(recent_messages),
						"with_responses": len(messages_with_responses),
						"without_responses": len(messages_without_responses),
						"response_rate": "0%"
					},
					"messages_with_responses": messages_with_responses,
					"messages_without_responses": messages_without_responses,
					"debug_info": "AI hook may not be triggered for real WhatsApp messages"
				}
			
		except Exception as e:
			log_debug("FAILED existing WhatsApp messages test", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"Existing WhatsApp messages test failed: {str(e)}",
				"error_details": {
					"error": str(e),
					"type": type(e).__name__,
					"traceback": traceback.format_exc()
				}
			}

	# Test 13: WhatsApp Real Flow Simulation
	def test_whatsapp_real_flow():
		"""Test the complete WhatsApp real flow - CREATE REAL WHATSAPP MESSAGE."""
		log_debug("Testing WhatsApp REAL FLOW simulation...")
		
		try:
			# Step 1: Create a REAL WhatsApp Message DocType record
			log_debug("Step 1: Creating REAL WhatsApp Message record...")
			
			# First, let's check what fields are available in WhatsApp Message DocType
			meta = frappe.get_meta("WhatsApp Message")
			available_fields = [field.fieldname for field in meta.fields]
			log_debug("Available WhatsApp Message fields", {"fields": available_fields})
			
			# Try to create the document with the correct field names
			whatsapp_doc = frappe.get_doc({
				"doctype": "WhatsApp Message",
				"type": "Incoming",
				"from": phone_number,
				"message": "ciao - test real flow",
				"content_type": "text",
				"status": "Sent"
			})
			
			# Save the document - this should trigger the hook
			whatsapp_doc.insert()
			log_debug("WhatsApp Message created successfully", {
				"doc_name": whatsapp_doc.name,
				"type": whatsapp_doc.type,
				"from_field": getattr(whatsapp_doc, 'from', None),
				"message": whatsapp_doc.message,
				"creation": str(whatsapp_doc.creation),
				"available_fields": available_fields
			})
			
			# Step 2: Check if AI hook was triggered
			log_debug("Step 2: Checking if AI hook was triggered...")
			
			# Wait a moment for async processing
			import time
			time.sleep(2)
			
			# Check if session files were created/updated
			from .agents.threads import _load_json_map
			thread_map = _load_json_map("ai_whatsapp_threads.json")
			response_map = _load_json_map("ai_response_map.json")
			
			log_debug("Session files after WhatsApp message", {
				"thread_map": thread_map,
				"response_map": response_map,
				"phone_in_threads": phone_number in thread_map,
				"phone_in_responses": phone_number in response_map
			})
			
			# Step 3: Check if AI responded
			log_debug("Step 3: Checking if AI responded...")
			
			# Look for outgoing messages from AI
			outgoing_messages = frappe.get_all(
				"WhatsApp Message",
				filters={
					"type": "Outgoing",
					"to": phone_number,
					"creation": [">=", whatsapp_doc.creation]
				},
				fields=["name", "message", "creation"],
				order_by="creation desc",
				limit=5
			)
			
			log_debug("Outgoing messages found", {
				"count": len(outgoing_messages),
				"messages": outgoing_messages
			})
			
			# Step 4: Check error logs for any issues
			log_debug("Step 4: Checking for errors...")
			
			recent_errors = frappe.get_all(
				"Error Log",
				filters={
					"creation": [">=", whatsapp_doc.creation],
					"method": ["like", "%whatsapp%"]
				},
				fields=["name", "error", "method", "creation"],
				order_by="creation desc",
				limit=5
			)
			
			log_debug("Recent WhatsApp-related errors", {
				"count": len(recent_errors),
				"errors": recent_errors
			})
			
			# Determine test result
			ai_responded = len(outgoing_messages) > 0
			hook_triggered = phone_number in thread_map
			
			if ai_responded:
				status = "pass"
				message = f"SUCCESS: AI responded! Found {len(outgoing_messages)} outgoing messages"
			elif hook_triggered:
				status = "warning"
				message = "PARTIAL: Hook triggered but AI didn't respond"
			else:
				status = "error"
				message = "FAILED: Hook not triggered or AI didn't process"
			
			return {
				"status": status,
				"message": message,
				"whatsapp_doc": {
					"name": whatsapp_doc.name,
					"type": whatsapp_doc.type,
					"from_field": getattr(whatsapp_doc, 'from', None),
					"message": whatsapp_doc.message,
					"creation": str(whatsapp_doc.creation),
					"status": whatsapp_doc.status
				},
				"ai_response": {
					"responded": ai_responded,
					"outgoing_messages": outgoing_messages,
					"hook_triggered": hook_triggered,
					"thread_created": phone_number in thread_map,
					"response_created": phone_number in response_map
				},
				"errors": recent_errors
			}
			
		except Exception as e:
			log_debug("FAILED WhatsApp real flow test", {"error": str(e), "traceback": traceback.format_exc()})
			return {
				"status": "error",
				"message": f"WhatsApp real flow test failed: {str(e)}",
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
	results["tests"]["ai_direct_execution"] = safe_test("AI Direct Execution", test_ai_direct_execution)
	results["tests"]["whatsapp_settings"] = safe_test("WhatsApp Settings", test_whatsapp_settings)
	results["tests"]["queue_processing"] = safe_test("Queue Processing", test_queue_processing)
	results["tests"]["fix_whatsapp_settings"] = safe_test("Fix WhatsApp Settings", test_fix_whatsapp_settings)
	
	# IMPORTANT: Run WhatsApp Real Flow AFTER fixing settings
	results["tests"]["whatsapp_real_flow"] = safe_test("WhatsApp Real Flow", test_whatsapp_real_flow)
	
	# Test real WhatsApp message after all fixes
	results["tests"]["real_whatsapp_message"] = safe_test("Real WhatsApp Message", test_real_whatsapp_message)
	
	# Check existing WhatsApp messages
	results["tests"]["existing_whatsapp_messages"] = safe_test("Existing WhatsApp Messages", test_existing_whatsapp_messages)
	
	# Verify settings are still correct after the test
	results["tests"]["verify_settings"] = safe_test("Verify Settings After Test", test_whatsapp_settings)
	
	log_debug("All AI tests completed")
	return results


@frappe.whitelist()
def run_ai_tests_api(phone_number: str = "+393926012793"):
	"""API endpoint to run AI tests."""
	return run_ai_tests(phone_number)
