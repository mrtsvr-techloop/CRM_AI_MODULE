import frappe
from typing import Any, Dict
from openai import OpenAI
from ai_module.agents.config import get_environment, get_session_mode


def _is_incoming_message(doc) -> bool:
	try:
		return (doc.type or "").lower() == "incoming"
	except Exception:
		return False


def _should_ignore(doc) -> bool:
	# Ignore reactions; only process actual messages
	content_type = (doc.get("content_type") or "").lower()
	return content_type == "reaction"


def _build_payload(doc) -> Dict[str, Any]:
	"""Build a structured payload for the AI from WhatsApp Message doc."""
	return {
		"name": doc.name,
		"type": doc.get("type"),
		"to": doc.get("to"),
		"from": doc.get("from"),
		"message_id": doc.get("message_id"),
		"is_reply": bool(doc.get("is_reply")),
		"reply_to_message_id": doc.get("reply_to_message_id"),
		"message_type": doc.get("message_type"),
		"use_template": bool(doc.get("use_template")),
		"template": doc.get("template"),
		"template_parameters": doc.get("template_parameters"),
		"template_header_parameters": doc.get("template_header_parameters"),
		"content_type": doc.get("content_type") or "text",
		"attach": doc.get("attach"),
		"message": doc.get("message"),
		"status": doc.get("status"),
		"reference_doctype": doc.get("reference_doctype"),
		"reference_name": doc.get("reference_name"),
		"creation": doc.get("creation"),
	}


def _thread_map_path() -> str:
	return frappe.utils.get_site_path("private", "files", "ai_whatsapp_threads.json")


def _load_thread_map() -> Dict[str, str]:
	try:
		path = _thread_map_path()
		import os, json  # noqa: WPS433 (std imports inside function for safety)
		if not os.path.exists(path):
			return {}
		with open(path, "r", encoding="utf-8") as f:
			data = f.read().strip()
			return json.loads(data) if data else {}
	except Exception:
		return {}


def _save_thread_map(mapping: Dict[str, str]) -> None:
	try:
		path = _thread_map_path()
		import os, json  # noqa: WPS433
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w", encoding="utf-8") as f:
			f.write(json.dumps(mapping))
	except Exception:
		pass


def _get_or_create_thread_for_phone(phone: str) -> str:
	"""Return a persistent OpenAI thread_id for a phone key, creating if absent."""
	phone_key = (phone or "").strip()
	if not phone_key:
		# Fallback: create a brand new thread (will be ephemeral)
		client = OpenAI()
		thread = client.beta.threads.create()
		return thread.id
	mapping = _load_thread_map()
	thread_id = mapping.get(phone_key)
	if thread_id and thread_id.startswith("thread_"):
		return thread_id
	client = OpenAI()
	thread = client.beta.threads.create()
	mapping[phone_key] = thread.id
	_save_thread_map(mapping)
	return thread.id


def on_whatsapp_after_insert(doc, method=None):
	"""DocEvent: after_insert for WhatsApp Message.
	Forward only Incoming non-reaction messages to the AI via Python include.
	"""
	try:
		if not _is_incoming_message(doc) or _should_ignore(doc):
			return

		payload = _build_payload(doc)

		# Enqueue lightweight job so we don't slow down insert path
		frappe.enqueue(
			"ai_module.integrations.whatsapp.process_incoming_whatsapp_message",
			queue="default",
			job_name=f"ai_whatsapp_{doc.name}",
			payload=payload,
			now=False,
		)
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="ai_module.integrations.whatsapp.on_whatsapp_after_insert",
		)


def process_incoming_whatsapp_message(payload: Dict[str, Any]):
	"""Background job: invoke AI with the given WhatsApp message payload.
	No HTTP is used; calls AI functions directly via Python import.
	Honors env for agent name and persists session/thread by sender phone.
	"""
	try:
		# Resolve agent name from env, fallback to a sensible default
		env = get_environment()
		agent_name = env.get("AI_AGENT_NAME") or "crm_ai"

		message_text = (payload.get("message") or "").strip()
		# Build a compact context string; agents can parse JSON-ish args if needed
		context_summary = {
			"reference_doctype": payload.get("reference_doctype"),
			"reference_name": payload.get("reference_name"),
			"from": payload.get("from"),
			"to": payload.get("to"),
			"message_id": payload.get("message_id"),
			"is_reply": payload.get("is_reply"),
			"reply_to_message_id": payload.get("reply_to_message_id"),
			"content_type": payload.get("content_type"),
			"attach": payload.get("attach"),
		}

		# Determine persistent session id strategy
		phone = (payload.get("from") or "").strip()
		mode = get_session_mode()
		if mode == "openai_threads":
			# Persist thread per phone number
			session_id = _get_or_create_thread_for_phone(phone)
		else:
			# For local sessions, using phone as session id maintains continuity
			session_id = f"whatsapp:{phone}" if phone else None

		# Import AI runtime directly; no HTTP
		from ai_module import api as ai_api

		# Compose an input that includes message and structured args as trailing JSON
		composed = message_text or ""
		if not composed:
			# For non-text messages, provide a stub plus metadata
			composed = f"[non-text:{payload.get('content_type')}]"
		# Attach lightweight args for the agent to parse
		composed = f"{composed}\n\n[args]: {frappe.as_json(context_summary)}"

		result = ai_api.ai_run_agent(agent_name=agent_name, message=composed, session_id=session_id, model=None)

		# Optional auto-reply via CRM, controlled by env AI_AUTOREPLY
		autoreply = (env.get("AI_AUTOREPLY") or "").strip().lower() in {"1", "true", "yes", "on"}
		if autoreply:
			reply_text = (result.get("final_output") or "").strip() if isinstance(result, dict) else ""
			if reply_text:
				try:
					from crm.api.whatsapp import create_whatsapp_message
					create_whatsapp_message(
						payload.get("reference_doctype"),
						payload.get("reference_name"),
						reply_text,
						payload.get("from"),
						"",
						payload.get("name"),
						"text",
					)
				except Exception:
					frappe.log_error(
						message=frappe.get_traceback(),
						title="ai_module.integrations.whatsapp.autoreply_failed",
					)

	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="ai_module.integrations.whatsapp.process_incoming_whatsapp_message",
		) 