from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from openai import OpenAI
import frappe


def _ensure_thread_id(session_id: Optional[str], client: OpenAI) -> str:
	"""Return a valid thread_id.

	- If a session_id looks like a thread id, verify it exists; if not, create a new thread.
	- If no valid session_id is provided, create a new thread.
	"""
	if session_id and session_id.startswith("thread_"):
		try:
			# Verify the thread exists
			client.beta.threads.retrieve(thread_id=session_id)
			return session_id
		except Exception:
			pass
	# Create a new thread if none exists or verification failed
	thread = client.beta.threads.create()
	return thread.id


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

	# Inject phone_from from thread map if not provided
	try:
		pf = (args.get("phone_from") or "").strip()
		if not pf:
			pf = _lookup_phone_from_thread(thread_id) or ""
			if pf:
				args["phone_from"] = pf
	except Exception:
		pass

	try:
		from .tool_registry import get_tool_impl
		impl = get_tool_impl(name)
		result = impl(**args)
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
	"""Send a user message via OpenAI Assistants Threads and return the assistant reply.

	- session_id: may be a thread_id (starting with "thread_"). If None or not a thread, a new thread is created.
	- assistant_id: the target OpenAI Assistant to run (configure this in env and create it via the OpenAI UI or API).
	- Returns dict with final_output (text), thread_id, assistant_id.
	"""
	client = OpenAI()
	thread_id = _ensure_thread_id(session_id, client)

	client.beta.threads.messages.create(
		thread_id=thread_id,
		role="user",
		content=message,
	)

	run = client.beta.threads.runs.create(
		thread_id=thread_id,
		assistant_id=assistant_id,
	)

	start = time.time()
	status = None
	while True:
		r = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
		status = r.status
		if status == "requires_action":
			# Tool calls needed
			tool_outputs = []
			for tc in r.required_action.submit_tool_outputs.tool_calls:  # type: ignore[attr-defined]
				# Attempt lazy registration of tool impl if missing; log tool name
				tool_name = getattr(getattr(tc, "function", None), "name", "")  # type: ignore[attr-defined]
				try:
					from .tools import ensure_tool_impl_registered
					registered = ensure_tool_impl_registered(tool_name)
					try:
						frappe.logger().info(f"[ai_module] tool_call name={tool_name} registered={registered}")
					except Exception:
						pass
				except Exception:
					pass
				output = _execute_function_tool(tc, thread_id)
				tool_outputs.append({"tool_call_id": tc.id, "output": output})
			client.beta.threads.runs.submit_tool_outputs(
				thread_id=thread_id,
				run_id=run.id,
				tool_outputs=tool_outputs,
			)
		elif status == "completed":
			break
		elif status in {"failed", "cancelled", "expired"}:
			raise RuntimeError(f"OpenAI run ended with status={status}")
		if time.time() - start > timeout_s:
			raise TimeoutError("Timed out waiting for OpenAI run to complete")
		time.sleep(poll_interval_s)

	msgs = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=5)
	final_text = ""
	# Prefer the most recent assistant message to avoid returning the user's echo
	if msgs.data:
		for m in msgs.data:
			if getattr(m, "role", None) == "assistant":
				parts = []
				for c in getattr(m, "content", []) or []:
					# Expect text entries; join them if multiple
					text = getattr(getattr(c, "text", None), "value", None)
					if text:
						parts.append(text)
				final_text = "\n".join(parts).strip()
				break
		# Fallback to latest message if no assistant message found
		if not final_text:
			m = msgs.data[0]
			parts = []
			for c in getattr(m, "content", []) or []:
				text = getattr(getattr(c, "text", None), "value", None)
				if text:
					parts.append(text)
			final_text = "\n".join(parts).strip()

	return {
		"final_output": final_text,
		"thread_id": thread_id,
		"assistant_id": assistant_id,
	} 