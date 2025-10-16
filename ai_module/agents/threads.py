from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import frappe
from openai import OpenAI, BadRequestError

from .logger_utils import get_resilient_logger

# Constants
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_POLL_INTERVAL = 0.75
MAX_ITERATIONS = 6
DEFAULT_MODEL = "gpt-4o-mini"

# Event types
OUTPUT_TEXT = "output_text"
MESSAGE = "message"
TOOL_USE = "tool_use"

# File paths
THREAD_MAP_FILE = "ai_whatsapp_threads.json"
RESPONSES_MAP_FILE = "ai_whatsapp_responses.json"


def _log():
	"""Get Frappe logger for threads module."""
	return get_resilient_logger("ai_module.threads")


def _get_map_path(filename: str) -> str:
	"""Get the full path for a JSON map file."""
	return frappe.utils.get_site_path("private", "files", filename)


def _load_json_map(filename: str) -> Dict[str, Any]:
	"""Load a JSON map from file. Returns empty dict if file doesn't exist."""
	path = _get_map_path(filename)
	if not os.path.exists(path):
		return {}
	
	with open(path, "r", encoding="utf-8") as f:
		data = f.read().strip()
		return json.loads(data) if data else {}


def _save_json_map(filename: str, mapping: Dict[str, Any]) -> None:
	"""Save a JSON map to file."""
	path = _get_map_path(filename)
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		json.dump(mapping, f)


def _ensure_thread_id(session_id: Optional[str]) -> str:
	"""Return a stable logical session id (no vendor thread objects)."""
	if session_id:
		return session_id
	return f"session_{int(time.time() * 1000)}"


def _lookup_phone_from_thread(thread_id: str) -> Optional[str]:
	"""Best-effort reverse lookup: find phone by session id from persisted map."""
	mapping = _load_json_map(THREAD_MAP_FILE)
	for phone, sid in mapping.items():
		if sid == thread_id:
			return str(phone)
	return None


def _coerce_tool_for_responses(tool: Dict[str, Any]) -> Dict[str, Any]:
	"""Convert a single Assistants-style tool to Responses format."""
	if not isinstance(tool, dict):
		return tool
	
	if (tool.get("type") or "").lower() != "function":
		return tool
	
	fn = tool.get("function") or {}
	name = (fn.get("name") or "").strip()
	if not name:
		raise ValueError("Tool schema missing function.name")
	
	return {
		"type": "function",
		"name": name,
		"description": fn.get("description") or "",
		"parameters": fn.get("parameters") or {"type": "object", "properties": {}},
	}


def _coerce_tools_for_responses(tools: Optional[List]) -> List[Dict[str, Any]]:
	"""Convert Assistants-style function tool schemas to Responses format.

	Accepts items like {"type":"function","function":{name,description,parameters}}
	and returns {"type":"function","name":name,"description":...,"parameters":...}
	Other tool definitions are passed through unchanged.
	"""
	if not tools:
		return []
	return [_coerce_tool_for_responses(t) for t in tools]


def _iter_response_events(resp: Any):
	"""Yield normalized response events (either top-level items or message content).

	Raises ValueError if the response shape is invalid to aid debugging.
	"""
	output = getattr(resp, "output", None)
	if output is None:
		raise ValueError("Responses API: missing 'output' field on response object")
	
	for item in output:
		itype = getattr(item, "type", None)
		if not itype:
			raise ValueError("Responses API: event without 'type' in output")
		
		if itype == MESSAGE:
			content = getattr(item, "content", None)
			if content is None:
				raise ValueError("Responses API: message event without 'content'")
			for c in content:
				yield c
		else:
			yield item


def _extract_tool_uses_and_text(resp: Any) -> Dict[str, Any]:
	"""Extract tool uses and assistant text from a Responses API response.

	Returns dict with keys: tool_uses (List[Any]), texts (List[str]).
	"""
	tool_uses: List[Any] = []
	texts: List[str] = []
	
	for ev in _iter_response_events(resp):
		evt_type = getattr(ev, "type", None)
		
		if evt_type == OUTPUT_TEXT:
			val = getattr(ev, "text", None)
			if val:
				texts.append(str(val))
		elif evt_type == TOOL_USE:
			tool_uses.append(ev)
		else:
			# Log unknown event types but continue processing (non-fatal)
			_log().warning(f"Responses API: unknown event type '{evt_type}' in output - ignoring")
	
	return {"tool_uses": tool_uses, "texts": texts}


def _load_responses_map() -> Dict[str, str]:
	"""Load session -> response_id mapping."""
	return _load_json_map(RESPONSES_MAP_FILE)


def _save_responses_map(mapping: Dict[str, str]) -> None:
	"""Save session -> response_id mapping."""
	_save_json_map(RESPONSES_MAP_FILE, mapping)


def _extract_tool_name_and_args(tool_call: Any) -> Tuple[str, Dict[str, Any]]:
	"""Extract function name and arguments from a tool call object."""
	# Responses API shape
	if hasattr(tool_call, "name") and hasattr(tool_call, "input"):
		name = str(getattr(tool_call, "name"))
		inp = getattr(tool_call, "input")
		if not isinstance(inp, dict):
			raise ValueError("tool_use.input must be a dict")
		return name, dict(inp)
	
	# Assistants API shape
	if hasattr(tool_call, "function"):
		fn = getattr(tool_call, "function")
		name = str(getattr(fn, "name"))
		args_json = getattr(fn, "arguments", None)
		args = json.loads(args_json) if args_json else {}
		return name, args
	
	raise ValueError("Unsupported tool_call shape")


def _sanitize_tool_args(args: Dict[str, Any], thread_id: str) -> Dict[str, Any]:
	"""Sanitize tool arguments: enforce phone_from from thread, remove unsafe phone fields."""
	sanitized = dict(args)
	
	# Get trusted phone from thread mapping
	thread_phone = _lookup_phone_from_thread(thread_id)
	if thread_phone:
		sanitized["phone_from"] = thread_phone
	
	# Remove any user-supplied phone fields (security)
	unsafe_keys = {"phone", "mobile", "mobile_no"}
	for key in list(sanitized.keys()):
		if str(key).lower() in unsafe_keys:
			sanitized.pop(key, None)
	
	return sanitized


def _save_contact_profile(args: Dict[str, Any], thread_id: str) -> None:
	"""Save contact profile after successful update_contact call."""
	from ai_module.integrations.whatsapp import _load_profile_map, _save_profile_map  # type: ignore
	
	profile = {
		"first_name": args.get("first_name"),
		"last_name": args.get("last_name"),
		"email": args.get("email"),
		"organization": args.get("organization"),
	}
	
	phone = _lookup_phone_from_thread(thread_id)
	if phone:
		profile_map = _load_profile_map()
		profile_map[str(phone)] = profile
		_save_profile_map(profile_map)


def _execute_function_tool(tool_call: Any, thread_id: str) -> str:
	"""Execute a function tool call locally using registered implementations."""
	# Extract tool name and arguments
	name, args = _extract_tool_name_and_args(tool_call)
	
	# Sanitize arguments for security
	args = _sanitize_tool_args(args, thread_id)
	
	# Get and execute tool implementation
	from .tool_registry import get_tool_impl
	impl = get_tool_impl(name)
	result = impl(**args)
	
	# Save profile on successful contact update
	if name == "update_contact" and isinstance(result, dict) and result.get("success"):
		_save_contact_profile(args, thread_id)
	
	# Return result as JSON string
	return json.dumps(result, default=str) if not isinstance(result, str) else result


def _build_initial_inputs(instructions: str, message: str) -> List[Dict[str, Any]]:
	"""Build the initial input messages for the AI."""
	inputs: List[Dict[str, Any]] = []
	
	if instructions:
		inputs.append({
			"role": "system",
			"content": [{"type": "input_text", "text": instructions}]
		})
	
	inputs.append({
		"role": "user",
		"content": [{"type": "input_text", "text": message}]
	})
	
	return inputs


def _process_tool_uses(
	tool_uses: List[Any],
	thread_id: str,
	inputs: List[Dict[str, Any]]
) -> None:
	"""Process and execute tool uses, appending results to inputs."""
	from .tools import ensure_tool_impl_registered
	
	for tool_use in tool_uses:
		tool_name = getattr(tool_use, "name", "")
		_log().info(f"Processing tool: {tool_name}")
		
		ensure_tool_impl_registered(tool_name)
		
		try:
			result = _execute_function_tool(tool_use, thread_id)
			_log().info(f"Tool {tool_name} executed successfully, result length: {len(str(result))}")
		except Exception as exc:
			_log().exception(f"Tool {tool_name} FAILED: {exc}")
			# Return error as tool result so AI knows it failed
			result = json.dumps({"error": str(exc), "success": False})
		
		inputs.append({
			"role": "tool",
			"content": [{"type": "output_text", "text": result}],
			"tool_call_id": getattr(tool_use, "id", None),
		})
		_log().debug(f"Added tool result to inputs: tool_call_id={getattr(tool_use, 'id', None)}")


def _create_ai_response(
	client: OpenAI,
	model: str,
	inputs: List[Dict[str, Any]],
	tools: List[Dict[str, Any]],
	prev_response_id: Optional[str]
) -> Any:
	"""Create an AI response using the Responses API."""
	kwargs: Dict[str, Any] = {
		"model": model,
		"input": inputs,
		"tools": tools
	}
	
	if prev_response_id:
		kwargs["previous_response_id"] = prev_response_id
	
	return client.responses.create(**kwargs)  # type: ignore[arg-type]


def run_with_responses_api(
	message: str,
	session_id: Optional[str],
	timeout_s: int = DEFAULT_TIMEOUT_SECONDS,
	poll_interval_s: float = DEFAULT_POLL_INTERVAL,
) -> Dict[str, Any]:
	"""Execute AI conversation using OpenAI Responses API.
	
	Uses the modern Responses API with previous_response_id for maintaining
	conversation state across multiple turns. No deprecated Assistants API.
	
	Args:
		message: User message to send
		session_id: Session ID for conversation continuity
		timeout_s: Maximum execution time in seconds
		poll_interval_s: Polling interval (unused with Responses API)
	
	Returns:
		Dict with final_output, thread_id (session_id), and model info
	"""
	from .assistant_update import get_current_instructions
	from .assistant_spec import get_assistant_tools
	from .config import apply_environment, get_environment
	
	# Apply environment variables (critical for OpenAI client initialization)
	apply_environment()
	
	# Get config
	env = get_environment()
	api_key = env.get("OPENAI_API_KEY")
	
	if not api_key:
		raise ValueError("OPENAI_API_KEY not configured. Set it in AI Assistant Settings or environment variables.")
	
	# Create OpenAI client with explicit API key
	client = OpenAI(api_key=api_key)
	thread_id = _ensure_thread_id(session_id)
	
	# Log request
	_log().info(
		f"AI request: message_len={len(message or '')} session={thread_id}"
	)
	
	# Prepare inputs
	instructions = (get_current_instructions() or "").strip()
	inputs = _build_initial_inputs(instructions, message)
	
	# Get tools and model config
	tools = _coerce_tools_for_responses(get_assistant_tools())
	model = env.get("AI_ASSISTANT_MODEL") or DEFAULT_MODEL
	
	# Load previous response ID for continuity
	resp_map = _load_responses_map()
	prev_id = resp_map.get(thread_id)
	
	# Log conversation continuity status
	if prev_id:
		_log().info(f"Continuing conversation: session={thread_id} prev_response={prev_id[:20]}...")
	else:
		_log().info(f"Starting new conversation: session={thread_id}")
	
	# Iterative processing loop
	final_text = ""
	start_time = time.time()
	iteration = 0
	current_response_id = prev_id  # Start with previous conversation's response_id
	tool_results_only: List[Dict[str, Any]] = []  # Track tool results for subsequent calls
	
	for _ in range(MAX_ITERATIONS):
		iteration += 1
		_log().info(f"AI loop iteration {iteration}/{MAX_ITERATIONS}")
		
		# Determine which inputs to send:
		# - First iteration: full inputs (system + user message)
		# - Subsequent iterations (tool calling): ONLY tool results
		# When using previous_response_id, OpenAI already has the conversation context
		if iteration == 1:
			inputs_to_send = inputs
		else:
			inputs_to_send = tool_results_only
			_log().debug(f"Sending only tool results ({len(tool_results_only)} items)")
		
		# Always use current_response_id for continuity (conversation + tool calling)
		if current_response_id:
			_log().debug(f"Using previous_response_id: {current_response_id[:20]}...")
		else:
			_log().debug("No previous_response_id (first message in new conversation)")
		
		# Create AI response
		try:
			# Debug: log inputs before calling API
			_log().debug(f"Calling API with {len(inputs_to_send)} input messages, prev_id={'Yes' if current_response_id else 'None'}")
			for idx, inp in enumerate(inputs_to_send):
				role = inp.get("role", "?")
				_log().debug(f"  Input[{idx}]: role={role}, has_tool_call_id={bool(inp.get('tool_call_id'))}")
			
			resp = _create_ai_response(client, model, inputs_to_send, tools, current_response_id)
			_log().info(f"Received response: id={getattr(resp, 'id', 'unknown')[:20]}...")
		except BadRequestError as exc:
			_log().error(f"AI API bad request: {exc}")
			_log().error(f"Request had {len(inputs_to_send)} inputs, prev_id={current_response_id[:20] if current_response_id else 'None'}")
			raise
		
		# Update current_response_id for next iteration (tool calling loop continuity)
		if getattr(resp, "id", None):
			current_response_id = str(resp.id)
			_log().debug(f"Updated current_response_id: {current_response_id[:20]}...")
		
		# Extract tool uses and text
		parsed = _extract_tool_uses_and_text(resp)
		tool_uses = parsed.get("tool_uses", [])
		
		# Log tool execution if present
		if tool_uses:
			tool_names = [getattr(t, "name", "unknown") for t in tool_uses]
			_log().info(f"Executing tools: {', '.join(tool_names)}")
		
		# Process tool calls if any
		if tool_uses:
			# Clear tool_results_only and populate with new tool results
			tool_results_only.clear()
			# Execute tools and add results to tool_results_only (not inputs!)
			_process_tool_uses(tool_uses, thread_id, tool_results_only)
			_log().info(f"Tools executed, continuing to next iteration with {len(tool_results_only)} tool results...")
			
			# Check timeout
			if time.time() - start_time > timeout_s:
				raise TimeoutError("Timed out waiting for AI response to complete")
			continue
		
		# No more tool calls - collect final text
		texts: List[str] = parsed.get("texts", [])
		final_text = "\n".join(texts).strip()
		_log().info(f"Final text collected: length={len(final_text)}")
		break
	
	# Save final response ID for next user message (conversation continuity)
	# Always save the final response_id (it will be complete by now)
	if current_response_id:
		resp_map[thread_id] = current_response_id
		_save_responses_map(resp_map)
		_log().info(f"Saved final response_id for session {thread_id}: {current_response_id[:20]}...")
	else:
		_log().debug("No response_id to save")
	
	# Log response
	_log().info(f"AI response: text_len={len(final_text or '')} session={thread_id}")
	
	return {
		"final_output": final_text,
		"thread_id": thread_id,
		"model": model,
	}


# Backward compatibility alias (deprecated name)
run_with_openai_threads = run_with_responses_api