"""OpenAI Assistants API integration for PDF context with file_search.

This module handles the legacy Assistants API specifically for RAG-based
PDF context retrieval using Vector Stores. It coexists with the modern
Responses API which is used for regular chat without PDF context.
"""

import frappe
from openai import OpenAI
from typing import Dict, Any, Optional
import time
import json
import threading


def _log():
	from .logger_utils import get_resilient_logger
	return get_resilient_logger("ai_module.assistants_api")


def _remove_pdf_citations(text: str) -> str:
	"""Remove PDF citation markers from text (e.g. 【12:0†file.pdf】).
	
	Args:
		text: Text potentially containing citation markers
	
	Returns:
		Text with all citation markers removed
	"""
	import re
	# Remove all text between 【 and 】 (including the brackets)
	cleaned_text = re.sub(r'【[^】]*】', '', text)
	return cleaned_text


def create_vector_store_with_file(file_path: str, store_name: str) -> str:
	"""Create a Vector Store and upload PDF file.
	
	Args:
		file_path: Local path to PDF file
		store_name: Name for the vector store
	
	Returns:
		Vector Store ID
	"""
	from .config import apply_environment, get_environment
	
	apply_environment()
	env = get_environment()
	api_key = env.get("OPENAI_API_KEY")
	
	if not api_key:
		frappe.throw("OPENAI_API_KEY not configured")
	
	client = OpenAI(api_key=api_key)
	
	# Upload file for assistants
	_log().info(f"Uploading PDF to OpenAI: {file_path}")
	with open(file_path, "rb") as f:
		file_obj = client.files.create(
			file=f,
			purpose="assistants"
		)
	
	# Create vector store with the file
	_log().info(f"Creating Vector Store: {store_name}")
	vector_store = client.vector_stores.create(
		name=store_name,
		file_ids=[file_obj.id]
	)
	
	# Wait for file processing
	_log().info(f"Waiting for file indexing in Vector Store: {vector_store.id}")
	max_wait = 300  # 5 minutes
	start = time.time()
	
	while time.time() - start < max_wait:
		vs = client.vector_stores.retrieve(vector_store.id)
		if vs.status == "completed":
			_log().info(f"Vector Store ready: {vector_store.id}")
			break
		elif vs.status == "failed":
			frappe.throw(f"Vector Store creation failed: {vs.last_error}")
		time.sleep(2)
	else:
		frappe.throw(f"Vector Store creation timeout after {max_wait}s")
	
	return vector_store.id


def create_assistant_with_vector_store(vector_store_id: str, instructions: str, model: str, name: Optional[str] = None) -> str:
	"""Create an Assistant with file_search tool AND function calling tools linked to Vector Store.
	
	Args:
		vector_store_id: ID of the vector store to attach
		instructions: System instructions for the assistant
		model: Model to use (e.g., gpt-4o-mini)
		name: Optional name for the assistant (defaults to "CRM Assistant with Knowledge Base")
	
	Returns:
		Assistant ID
	"""
	from .config import apply_environment, get_environment
	from .assistant_spec import get_assistant_tools
	
	apply_environment()
	env = get_environment()
	api_key = env.get("OPENAI_API_KEY")
	
	if not api_key:
		frappe.throw("OPENAI_API_KEY not configured")
	
	client = OpenAI(api_key=api_key)
	
	_log().info(f"Creating Assistant with file_search for Vector Store: {vector_store_id}")
	
	# Get all function calling tools from the system
	function_tools = get_assistant_tools()
	
	# Build tools list: file_search + all function tools
	tools = [{"type": "file_search"}]
	
	# Add function calling tools (convert from Responses API format to Assistants API format)
	for tool in function_tools:
		if tool.get("type") == "function":
			tools.append({
				"type": "function",
				"function": tool["function"]
			})
	
	_log().info(f"Creating Assistant with {len(tools)} tools (1 file_search + {len(function_tools)} functions)")
	
	assistant_name = name or "CRM Assistant with Knowledge Base"
	assistant = client.beta.assistants.create(
		name=assistant_name,
		instructions=instructions,
		model=model,
		tools=tools,
		tool_resources={
			"file_search": {
				"vector_store_ids": [vector_store_id]
			}
		}
	)
	
	_log().info(f"Assistant created: {assistant.id} (name: {assistant_name})")
	return assistant.id


def update_assistant_on_openai(assistant_id: str, instructions: Optional[str] = None, model: Optional[str] = None, name: Optional[str] = None, vector_store_id: Optional[str] = None) -> bool:
	"""Update an existing Assistant on OpenAI.
	
	Args:
		assistant_id: OpenAI Assistant ID to update
		instructions: Optional new instructions (if None, keeps existing)
		model: Optional new model (if None, keeps existing)
		name: Optional new name (if None, keeps existing)
		vector_store_id: Optional new vector store ID (if None, keeps existing)
	
	Returns:
		True if update succeeded, False otherwise
	"""
	from .config import apply_environment, get_environment
	from .assistant_spec import get_assistant_tools
	
	try:
		apply_environment()
		env = get_environment()
		api_key = env.get("OPENAI_API_KEY")
		
		if not api_key:
			_log().warning("OPENAI_API_KEY not configured")
			return False
		
		client = OpenAI(api_key=api_key)
		
		# Verify assistant exists
		try:
			assistant = client.beta.assistants.retrieve(assistant_id)
		except Exception as e:
			_log().warning(f"Assistant {assistant_id} not found on OpenAI: {e}")
			return False
		
		# Build update payload with only changed fields
		update_data = {}
		
		if instructions is not None:
			update_data["instructions"] = instructions
		
		if model is not None:
			update_data["model"] = model
		
		if name is not None:
			update_data["name"] = name
		
		# Handle vector store update
		if vector_store_id is not None:
			# Get all function calling tools from the system
			function_tools = get_assistant_tools()
			
			# Build tools list: file_search + all function tools
			tools = [{"type": "file_search"}]
			
			# Add function calling tools
			for tool in function_tools:
				if tool.get("type") == "function":
					tools.append({
						"type": "function",
						"function": tool["function"]
					})
			
			update_data["tools"] = tools
			update_data["tool_resources"] = {
				"file_search": {
					"vector_store_ids": [vector_store_id]
				}
			}
		
		if not update_data:
			_log().debug(f"No changes to apply to assistant {assistant_id}")
			return True
		
		_log().info(f"Updating Assistant {assistant_id} with fields: {list(update_data.keys())}")
		client.beta.assistants.update(assistant_id, **update_data)
		
		_log().info(f"Assistant {assistant_id} updated successfully")
		return True
		
	except Exception as e:
		_log().error(f"Failed to update assistant {assistant_id}: {e}")
		return False


def run_with_assistants_api(
	message: str,
	assistant_id: str,
	session_id: Optional[str] = None,
	timeout_s: int = 120  # Increased timeout to 120s for complex queries with PDF context
) -> Dict[str, Any]:
	"""Run conversation using Assistants API with file_search.
	
	This maintains conversation state using OpenAI Threads (different from
	Responses API which uses previous_response_id).
	
	Args:
		message: User message
		assistant_id: OpenAI Assistant ID
		session_id: Session ID for thread continuity
		timeout_s: Max execution time
	
	Returns:
		Dict with final_output, thread_id, and model info
	"""
	from .config import apply_environment, get_environment
	
	apply_environment()
	env = get_environment()
	api_key = env.get("OPENAI_API_KEY")
	
	if not api_key:
		raise ValueError("OPENAI_API_KEY not configured")
	
	client = OpenAI(api_key=api_key)
	
	# PRODUCTION-READY: Serializza messaggi dello stesso utente usando thread lock
	# Ogni numero di telefono ha il suo lock, quindi utenti diversi possono interagire simultaneamente
	# Solo lo stesso utente che invia messaggi rapidi viene serializzato
	lock = _get_thread_lock(session_id or "default")
	
	with lock:
		# Get or create thread for this session
		thread_id = _get_or_create_thread(client, session_id)
		
		_log().info(f"AI request (Assistants API): message_len={len(message)} thread={thread_id}")
		
		# Check for active runs and wait for them to complete
		# Since we're serialized by lock, this should rarely be needed,
		# but handles edge cases where a run might still be active
		max_wait_time = 10  # Reduced since we're serialized
		wait_start = time.time()
		
		while True:
			try:
				runs = client.beta.threads.runs.list(thread_id=thread_id, limit=1)
				active_run = None
				
				for run in runs.data:
					if run.status in ["queued", "in_progress", "requires_action"]:
						active_run = run
						break
				
				if not active_run:
					# No active run, safe to add message
					break
				
				# Check if we've waited too long
				if time.time() - wait_start > max_wait_time:
					_log().warning(
						f"Active run {active_run.id} still running after {max_wait_time}s. "
						f"Cancelling to allow new message."
					)
					try:
						client.beta.threads.runs.cancel(thread_id=thread_id, run_id=active_run.id)
						time.sleep(0.5)  # Wait for cancellation
						break
					except Exception as cancel_error:
						_log().warning(f"Failed to cancel run {active_run.id}: {cancel_error}")
						break
				
				# Wait a bit and check again
				_log().debug(f"Waiting for run {active_run.id} to complete (status: {active_run.status})")
				time.sleep(1)
				
			except Exception as list_error:
				_log().debug(f"Could not check for active runs: {list_error}")
				break
		
		# Add message to thread
		client.beta.threads.messages.create(
			thread_id=thread_id,
			role="user",
			content=message
		)
		
		# Run assistant (inside lock to prevent race conditions)
		try:
			run = client.beta.threads.runs.create(
				thread_id=thread_id,
				assistant_id=assistant_id
			)
		except Exception as e:
			error_msg = str(e)
			_log().error(f"Failed to create run: {error_msg}")
			
			# If assistant doesn't exist, provide helpful error
			if "assistant" in error_msg.lower() or "not found" in error_msg.lower():
				raise Exception(
					f"Assistant {assistant_id} not found. Please re-upload the PDF in AI Assistant Settings "
					f"to recreate the Assistant with the latest configuration."
				)
			raise
		
		# Release lock immediately after creating run to allow next message from same user
		# The run will continue processing asynchronously on OpenAI side
		# This ensures we can handle multiple rapid messages from same user
		# Note: Lock is automatically released when exiting 'with lock:' block
	
	# Poll for completion and handle tool calls (outside lock)
	# Multiple runs from same user can poll concurrently, but run creation is serialized
	start = time.time()
	while time.time() - start < timeout_s:
		run = client.beta.threads.runs.retrieve(
			thread_id=thread_id,
			run_id=run.id
		)
		
		if run.status == "completed":
			break
		elif run.status == "requires_action":
			# Assistant wants to call tools
			_log().info(f"Assistant requires action: handling tool calls")
			_handle_tool_calls(client, thread_id, run, session_id)
			# Continue polling after submitting tool outputs
		elif run.status in ["failed", "cancelled", "expired"]:
			error_detail = getattr(run, 'last_error', None)
			error_msg = f"Run {run.status}"
			
			if error_detail:
				error_code = getattr(error_detail, 'code', 'unknown')
				error_message = getattr(error_detail, 'message', 'Unknown error')
				error_msg += f": {error_code} - {error_message}"
				
				# Provide helpful message for common errors
				if error_code == 'server_error':
					error_msg += "\n\nThis may be a temporary OpenAI issue. Please try again in a moment."
				elif 'rate_limit' in error_code:
					error_msg += "\n\nOpenAI rate limit reached. Please wait a moment and try again."
			
			_log().error(error_msg)
			raise Exception(error_msg)
		
		time.sleep(1)
	else:
		# Timeout occurred - try to get partial response if available
		_log().warning(f"Assistant run timeout after {timeout_s}s, attempting to retrieve partial response")
		try:
			messages = client.beta.threads.messages.list(
				thread_id=thread_id,
				order="desc",
				limit=1
			)
			if messages.data:
				message_content = messages.data[0].content[0]
				if hasattr(message_content, 'text'):
					partial_text = message_content.text.value
					if partial_text and partial_text.strip():
						_log().info(f"Retrieved partial response despite timeout: {len(partial_text)} chars")
						# Return partial response instead of raising error
						return {
							"final_output": partial_text,
							"thread_id": thread_id,
							"model": env.get("AI_ASSISTANT_MODEL") or "gpt-4o-mini",
							"partial": True
						}
		except Exception as partial_err:
			_log().warning(f"Could not retrieve partial response: {partial_err}")
		
		raise TimeoutError(f"Assistant run timeout after {timeout_s}s")
	
	# Get latest message
	messages = client.beta.threads.messages.list(
		thread_id=thread_id,
		order="desc",
		limit=1
	)
	
	if not messages.data:
		raise Exception("No response from assistant")
	
	# Extract text from message
	message_content = messages.data[0].content[0]
	if hasattr(message_content, 'text'):
		response_text = message_content.text.value
	else:
		response_text = str(message_content)
	
	# Remove PDF citations (e.g. 【12:0†file.pdf】)
	response_text = _remove_pdf_citations(response_text)
	
	_log().info(f"AI response (Assistants API): text_len={len(response_text)} thread={thread_id}")
	
	return {
		"final_output": response_text,
		"thread_id": thread_id,
		"model": run.model,
		"api_type": "assistants"
	}


def _handle_tool_calls(client: OpenAI, thread_id: str, run: Any, session_id: Optional[str] = None) -> None:
	"""Handle tool calls requested by the Assistant.
	
	Args:
		client: OpenAI client
		thread_id: Thread ID
		run: Run object with requires_action status
		session_id: Session ID to inject phone_from
	"""
	from .tool_registry import get_tool_impl
	from .threads import _sanitize_tool_args
	
	if not run.required_action or not run.required_action.submit_tool_outputs:
		return
	
	tool_calls = run.required_action.submit_tool_outputs.tool_calls
	tool_outputs = []
	
	for tool_call in tool_calls:
		function_name = tool_call.function.name
		arguments = json.loads(tool_call.function.arguments)
		
		_log().info(f"Executing tool: {function_name} with args: {arguments}")
		
		try:
			# Inject phone_from from session mapping (security)
			if session_id:
				arguments = _sanitize_tool_args(arguments, session_id)
			
			# Get tool implementation
			tool_func = get_tool_impl(function_name)
			
			if not tool_func:
				output = {"error": f"Tool {function_name} not found"}
			else:
				# Execute tool
				result = tool_func(**arguments)
				output = result if isinstance(result, dict) else {"result": result}
		
		except Exception as e:
			_log().error(f"Tool execution error: {function_name} - {str(e)}")
			output = {"error": str(e)}
		
		# Serialize output, handling datetime and other non-JSON types
		try:
			output_json = json.dumps(output, default=_json_serializer)
		except Exception as e:
			_log().error(f"JSON serialization error: {str(e)}")
			output_json = json.dumps({"error": "Serialization failed", "message": str(e)})
		
		tool_outputs.append({
			"tool_call_id": tool_call.id,
			"output": output_json
		})
		
		_log().info(f"Tool {function_name} output: {output}")
	
	# Submit all tool outputs back to the Assistant
	client.beta.threads.runs.submit_tool_outputs(
		thread_id=thread_id,
		run_id=run.id,
		tool_outputs=tool_outputs
	)
	
	_log().info(f"Submitted {len(tool_outputs)} tool outputs")


def _json_serializer(obj):
	"""JSON serializer for objects not serializable by default json code."""
	from datetime import datetime, date
	
	if isinstance(obj, (datetime, date)):
		return obj.isoformat()
	
	# Try to convert to string for other types
	try:
		return str(obj)
	except Exception:
		return None


def _get_or_create_thread(client: OpenAI, session_id: Optional[str]) -> str:
	"""Get existing thread or create new one for session.
	
	Maps session_id to OpenAI thread_id using local file storage.
	Validates that thread still exists on OpenAI before reusing.
	"""
	if not session_id:
		# No session, create new thread
		thread = client.beta.threads.create()
		return thread.id
	
	# Check if thread exists for this session
	thread_map_path = _get_thread_map_path()
	thread_map = _load_json_file(thread_map_path)
	
	if session_id in thread_map:
		thread_id = thread_map[session_id]
		_log().debug(f"Found cached thread {thread_id} for session {session_id}")
		
		# Verify thread still exists on OpenAI
		try:
			client.beta.threads.retrieve(thread_id)
			_log().debug(f"Thread {thread_id} verified on OpenAI")
			return thread_id
		except Exception as e:
			_log().warning(f"Cached thread {thread_id} not found on OpenAI: {e}. Creating new thread.")
			# Remove invalid thread from cache
			del thread_map[session_id]
			_save_json_file(thread_map_path, thread_map)
	
	# Create new thread and save mapping
	thread = client.beta.threads.create()
	thread_map[session_id] = thread.id
	_save_json_file(thread_map_path, thread_map)
	
	_log().info(f"Created new thread {thread.id} for session {session_id}")
	return thread.id


# Thread locks per serializzare messaggi dello stesso utente quando usa Assistants API
# Production-ready: previene race conditions quando lo stesso utente invia messaggi rapidi
_thread_locks: Dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()  # Lock per gestire il dict dei locks


def _get_thread_lock(session_id: str) -> threading.Lock:
	"""Get or create a thread lock for a session_id.
	
	This ensures messages from the same user are processed sequentially
	when using Assistants API (which doesn't allow concurrent runs on same thread).
	"""
	with _locks_lock:
		if session_id not in _thread_locks:
			_thread_locks[session_id] = threading.Lock()
		return _thread_locks[session_id]


def _get_thread_map_path() -> str:
	"""Get path to thread mapping file."""
	import os
	site_path = frappe.utils.get_site_path()
	return os.path.join(site_path, "private", "files", "ai_assistants_threads.json")


def _load_json_file(path: str) -> dict:
	"""Load JSON file or return empty dict."""
	import json
	import os
	
	if not os.path.exists(path):
		return {}
	
	try:
		with open(path, "r") as f:
			content = f.read().strip()
			return json.loads(content) if content else {}
	except Exception:
		return {}


def _save_json_file(path: str, data: dict) -> None:
	"""Save dict to JSON file."""
	import json
	import os
	
	# Ensure directory exists with proper permissions
	dir_path = os.path.dirname(path)
	os.makedirs(dir_path, mode=0o755, exist_ok=True)
	
	try:
		with open(path, "w") as f:
			json.dump(data, f, indent=2)
		# Set file permissions
		os.chmod(path, 0o644)
	except Exception as e:
		_log().error(f"Failed to save JSON file {path}: {e}")
		raise


def delete_vector_store(vector_store_id: str) -> bool:
	"""Delete a Vector Store from OpenAI."""
	from .config import apply_environment, get_environment
	
	try:
		apply_environment()
		env = get_environment()
		api_key = env.get("OPENAI_API_KEY")
		
		if not api_key:
			return False
		
		client = OpenAI(api_key=api_key)
		client.vector_stores.delete(vector_store_id)
		
		_log().info(f"Deleted Vector Store: {vector_store_id}")
		return True
	except Exception as e:
		_log().warning(f"Failed to delete Vector Store {vector_store_id}: {e}")
		return False


def delete_assistant(assistant_id: str) -> bool:
	"""Delete an Assistant from OpenAI."""
	from .config import apply_environment, get_environment
	
	try:
		apply_environment()
		env = get_environment()
		api_key = env.get("OPENAI_API_KEY")
		
		if not api_key:
			return False
		
		client = OpenAI(api_key=api_key)
		client.beta.assistants.delete(assistant_id)
		
		_log().info(f"Deleted Assistant: {assistant_id}")
		return True
	except Exception as e:
		_log().warning(f"Failed to delete Assistant {assistant_id}: {e}")
		return False

