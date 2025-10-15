from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from openai import OpenAI
import frappe


def _ensure_thread_id(session_id: Optional[str]) -> str:
	"""Return a stable logical session id (no vendor thread objects)."""
	if session_id:
		return session_id
	return f"session_{int(time.time() * 1000)}"


def _lookup_phone_from_thread(thread_id: str) -> Optional[str]:
	"""Best-effort reverse lookup: find phone by thread id from persisted map."""
	try:
		path = frappe.utils.get_site_path("private", "files", "ai_whatsapp_threads.json")
		import os, json as _json  # noqa: WPS433
		if not os.path.exists(path):
			return None
		with open(path, "r", encoding="utf-8") as f:
			data = f.read().strip()
			mapping = _json.loads(data) if data else {}
		for phone, tid in mapping.items():
			if tid == thread_id:
				return str(phone)
		return None
	except Exception:
		return None


def _coerce_tools_for_responses(tools: Optional[list]) -> list:
	"""Convert Assistants-style function tool schemas to Responses format.

	Accepts items like {"type":"function","function":{name,description,parameters}}
	and returns {"type":"function","name":name,"description":...,"parameters":...}
	Other tool definitions are passed through unchanged.
	"""
	coerced: list = []
	for t in (tools or []):
		try:
			if isinstance(t, dict) and (t.get("type") or "").lower() == "function":
				fn = t.get("function") or {}
				name = (fn.get("name") or "").strip()
				params = fn.get("parameters") or {"type": "object", "properties": {}}
				desc = fn.get("description") or ""
				coerced.append({
					"type": "function",
					"name": name,
					"description": desc,
					"parameters": params,
				})
			else:
				coerced.append(t)
		except Exception:
			coerced.append(t)
	return coerced


def _responses_map_path() -> str:
	return frappe.utils.get_site_path("private", "files", "ai_whatsapp_responses.json")


def _load_responses_map() -> Dict[str, str]:
	try:
		path = _responses_map_path()
		import os, json as _json  # noqa: WPS433
		if not os.path.exists(path):
			return {}
		with open(path, "r", encoding="utf-8") as f:
			data = f.read().strip()
			return _json.loads(data) if data else {}
	except Exception:
		return {}


def _save_responses_map(mapping: Dict[str, str]) -> None:
	try:
		path = _responses_map_path()
		import os, json as _json  # noqa: WPS433
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w", encoding="utf-8") as f:
			f.write(_json.dumps(mapping))
	except Exception:
		pass


def _execute_function_tool(tool_call: Any, thread_id: str) -> str:
	"""Execute a function tool call locally using registered implementations.

	If no implementation is found, return an informative error string.
	"""
	try:
		name = tool_call.function.name  # type: ignore[attr-defined]
		args_json = tool_call.function.arguments  # type: ignore[attr-defined]
		args = json.loads(args_json) if args_json else {}
	except Exception:
		return "{\"error\": \"invalid_tool_call\"}"

	# Enforce phone sourcing from thread map and never from user-provided args
	try:
		thread_phone = _lookup_phone_from_thread(thread_id) or ""
		if thread_phone:
			# Always override any incoming phone_from with the trusted thread phone
			args["phone_from"] = thread_phone
		# Globally drop any user-supplied phone fields (allow only phone_from)
		for key in list(args.keys()):
			k = str(key).lower()
			if k in {"phone", "mobile", "mobile_no"}:
				args.pop(key, None)
	except Exception:
		pass

	try:
		from .tool_registry import get_tool_impl
		impl = get_tool_impl(name)
		result = impl(**args)
		# If contact was updated/created, persist a lightweight profile for this thread phone
		try:
			if name == "update_contact" and isinstance(result, dict) and bool(result.get("success")):
				from ai_module.integrations.whatsapp import _load_profile_map, _save_profile_map  # type: ignore
				prof = {
					"first_name": args.get("first_name"),
					"last_name": args.get("last_name"),
					"email": args.get("email"),
					"organization": args.get("organization"),
				}
				# Resolve phone from thread map
				phone = _lookup_phone_from_thread(thread_id) or ""
				if phone:
					m = _load_profile_map()
					m[str(phone)] = prof
					_save_profile_map(m)
		except Exception:
			pass
		return json.dumps(result, default=str) if not isinstance(result, str) else result
	except KeyError:
		return json.dumps({"error": f"no_implementation_for_{name}"})
	except Exception as exc:
		return json.dumps({"error": str(exc)})


def run_with_openai_threads(
	message: str,
	session_id: Optional[str],
	assistant_id: str,
	timeout_s: int = 120,
	poll_interval_s: float = 0.75,
) -> Dict[str, Any]:
	"""Use Responses API (latest) with previous_response_id; preserve signature."""
	from .assistant_update import get_current_instructions
	from .assistant_spec import get_assistant_tools
	from .config import get_environment

	client = OpenAI()
	thread_id = _ensure_thread_id(session_id)

	# Before sending to AI
	try:
		import logging as _logging  # noqa: WPS433
		_logging.getLogger(__name__).info(
			"[ai_module] before_send message_len=%s session=%s assistant=%s",
			len(message or ""),
			thread_id,
			assistant_id,
		)
		frappe.logger().info(
			f"[ai_module] before_send message_len={len(message or '')} session={thread_id} assistant={assistant_id}"
		)
	except Exception:
		pass

	instr = (get_current_instructions() or "").strip()
	inputs: list[Dict[str, Any]] = []
	if instr:
		inputs.append({"role": "system", "content": [{"type": "input_text", "text": instr}]})
	inputs.append({"role": "user", "content": [{"type": "input_text", "text": message}]})

	tools = _coerce_tools_for_responses(get_assistant_tools() or [])
	model = get_environment().get("AI_ASSISTANT_MODEL") or "gpt-4o-mini"

	resp_map = _load_responses_map()
	prev_id = resp_map.get(thread_id)

	final_text = ""
	start = time.time()
	max_iters = 6
	for _ in range(max_iters):
		kwargs: Dict[str, Any] = {"model": model, "input": inputs, "tools": tools}
		if prev_id:
			kwargs["previous_response_id"] = prev_id
		resp = client.responses.create(**kwargs)  # type: ignore[arg-type]
		# Save current id for next turns
		try:
			if getattr(resp, "id", None):
				resp_map[thread_id] = str(resp.id)
				_save_responses_map(resp_map)
		except Exception:
			pass

		# Tool calls
		tool_uses: list[Any] = []
		try:
			for item in getattr(resp, "output", []) or []:
				if getattr(item, "type", "") == "tool_use":
					tool_uses.append(item)
		except Exception:
			tool_uses = []

		if tool_uses:
			for tu in tool_uses:
				try:
					from .tools import ensure_tool_impl_registered
					ensure_tool_impl_registered(getattr(tu, "name", ""))
				except Exception:
					pass
				result = _execute_function_tool(tu, thread_id)
				inputs.append({
					"role": "tool",
					"content": [{"type": "output_text", "text": result}],
					"tool_call_id": getattr(tu, "id", None),
				})
			if time.time() - start > timeout_s:
				raise TimeoutError("Timed out waiting for OpenAI response to complete")
			continue

		# Collect final text
		texts: list[str] = []
		try:
			for item in getattr(resp, "output", []) or []:
				if getattr(item, "type", "") == "output_text":
					val = getattr(item, "text", None)
					if val:
						texts.append(str(val))
		except Exception:
			pass
		final_text = "\n".join(texts).strip()
		break

	# Before returning response
	try:
		import logging as _logging  # noqa: WPS433
		_logging.getLogger(__name__).info(
			"[ai_module] before_return text_len=%s session=%s",
			len(final_text or ""),
			thread_id,
		)
		frappe.logger().info(
			f"[ai_module] before_return text_len={len(final_text or '')} session={thread_id}"
		)
	except Exception:
		pass

	return {
		"final_output": final_text,
		"thread_id": thread_id,
		"assistant_id": assistant_id,
	}