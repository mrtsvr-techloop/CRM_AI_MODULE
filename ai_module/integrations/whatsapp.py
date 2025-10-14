import frappe
from typing import Any, Dict
from openai import OpenAI
from ai_module.agents.config import get_environment, apply_environment


def _is_incoming_message(doc) -> bool:
	try:
		return (doc.type or "").lower() == "incoming"
	except Exception:
		return False


def _should_ignore(doc) -> bool:
	# Ignore reactions; only process actual messages
	content_type = (doc.get("content_type") or "").lower()
	return content_type == "reaction"


def _is_dev_env() -> bool:
	"""Return True when running in developer/local environment.

	Heuristics: Frappe developer_mode or localhost URL.
	"""
	try:
		if int(getattr(frappe.conf, "developer_mode", 0) or 0) == 1:
			return True
		url = str(frappe.utils.get_url() or "")
    return url.startswith("http://localhost") or url.startswith("http://127.0.0.1")
	except Exception:
		return False


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


def _lang_map_path() -> str:
	return frappe.utils.get_site_path("private", "files", "ai_whatsapp_lang.json")


def _handoff_map_path() -> str:
	return frappe.utils.get_site_path("private", "files", "ai_whatsapp_handoff.json")


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


def _load_lang_map() -> Dict[str, str]:
	try:
		path = _lang_map_path()
		import os, json  # noqa: WPS433
		if not os.path.exists(path):
			return {}
		with open(path, "r", encoding="utf-8") as f:
			data = f.read().strip()
			return json.loads(data) if data else {}
	except Exception:
		return {}


def _save_lang_map(mapping: Dict[str, str]) -> None:
	try:
		path = _lang_map_path()
		import os, json  # noqa: WPS433
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w", encoding="utf-8") as f:
			f.write(json.dumps(mapping))
	except Exception:
		pass


def _load_handoff_map() -> Dict[str, float]:
	try:
		path = _handoff_map_path()
		import os, json  # noqa: WPS433
		if not os.path.exists(path):
			return {}
		with open(path, "r", encoding="utf-8") as f:
			data = f.read().strip()
			return json.loads(data) if data else {}
	except Exception:
		return {}


def _save_handoff_map(mapping: Dict[str, float]) -> None:
	try:
		path = _handoff_map_path()
		import os, json  # noqa: WPS433
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w", encoding="utf-8") as f:
			f.write(json.dumps(mapping))
	except Exception:
		pass


def _mark_human_activity(phone: str) -> None:
	"""Record the time a human sent an outgoing message to this phone."""
	try:
		import time  # noqa: WPS433
		key = (phone or "").strip()
		if not key:
			return
		m = _load_handoff_map()
		m[key] = float(time.time())
		_save_handoff_map(m)
	except Exception:
		pass


def _human_cooldown_seconds() -> int:
	try:
        # Prefer DocType override when enabled
        sec = None
        try:
            doc = frappe.get_single("AI Assistant Settings")
            if getattr(doc, "use_settings_override", 0):
                sec = int(getattr(doc, "wa_human_cooldown_seconds", 0) or 0)
        except Exception:
            sec = None
        if sec and sec > 0:
            return int(sec)
        val = (get_environment().get("AI_HUMAN_COOLDOWN_SECONDS") or "").strip()
        return int(val) if str(val).isdigit() else 300
	except Exception:
		return 300


def _is_human_active(phone: str) -> bool:
	"""Return True if a human messaged this phone within the cooldown window."""
	try:
		import time  # noqa: WPS433
		key = (phone or "").strip()
		if not key:
			return False
		m = _load_handoff_map()
		last_ts = float(m.get(key) or 0.0)
		if last_ts <= 0:
			return False
		return (time.time() - last_ts) < _human_cooldown_seconds()
	except Exception:
		return False


def _detect_language(text: str) -> str:
	"""Best-effort language detection.

	- Tries langid if available; else naive keyword heuristics; defaults to 'it'.
	"""
	try:
		import langid  # type: ignore
		code, _ = langid.classify(text or "")
		return (code or "it").split("-")[0]
	except Exception:
		pass
	# Simple heuristic
	val = (text or "").lower()
	try:
		if any(w in val for w in ["hola", "gracias", "buenos", "por favor"]):
			return "es"
		if any(w in val for w in ["bonjour", "merci", "s'il vous plaît", "salut"]):
			return "fr"
		if any(w in val for w in ["hello", "thanks", "please", "hi", "the "]):
			return "en"
		if any(w in val for w in ["ciao", "grazie", "per favore", "buongiorno"]):
			return "it"
		return "it"
	except Exception:
		return "it"


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
		# Ensure env is applied for worker context
		apply_environment()
		# Track human activity on outgoing messages and exit early
		if (doc.type or "").lower() == "outgoing":
			try:
				_mark_human_activity(doc.get("to"))
			except Exception:
				pass
			return

		# Skip non-incoming messages and reactions
		if not _is_incoming_message(doc) or _should_ignore(doc):
			return

		# If a human interacted recently, do not run AI
		try:
			if _is_human_active(doc.get("from")):
				try:
					frappe.logger().info("[ai_module] human active recently; skipping AI reply")
				except Exception:
					pass
				return
		except Exception:
			pass

		# Internal: ensure a Contact exists for this incoming phone (no external API)
		try:
			from crm.api.workflow import ensure_contact_from_message
			ensure_contact_from_message(message_name=doc.name)
		except Exception:
			try:
				frappe.logger().warning("[ai_module] ensure_contact_from_message failed (non-fatal)")
			except Exception:
				pass

		# Persist detected language per phone for later context use
		try:
			phone_key = (doc.get("from") or "").strip()
			lang_map = _load_lang_map()
			lang_detected = _detect_language(doc.get("message") or "")
			if phone_key and lang_detected:
				prev = lang_map.get(phone_key)
				if prev != lang_detected:
					lang_map[phone_key] = lang_detected
					_save_lang_map(lang_map)
		except Exception:
			pass

		payload = _build_payload(doc)
		# Trace enqueue intent.
		try:
			frappe.logger().info(f"[ai_module] enqueue whatsapp job for {doc.name} payload keys={list(payload.keys())}")
		except Exception:
			pass

        # Inline processing: prefer DocType override; else default ON in dev when env unset
		try:
            env = get_environment()
            raw_inline = (env.get("AI_WHATSAPP_INLINE") or "").strip().lower()
            # DocType override
            try:
                doc_settings = frappe.get_single("AI Assistant Settings")
                if getattr(doc_settings, "use_settings_override", 0):
                    inline = bool(getattr(doc_settings, "wa_force_inline", 0))
                else:
                    inline = raw_inline in {"1", "true", "yes", "on"} or (raw_inline == "" and _is_dev_env())
            except Exception:
                inline = raw_inline in {"1", "true", "yes", "on"} or (raw_inline == "" and _is_dev_env())
			if inline:
				try:
					frappe.logger().info("[ai_module] whatsapp inline processing active; executing synchronously")
				except Exception:
					pass
				process_incoming_whatsapp_message(payload)
				return
		except Exception:
			pass

		# Enqueue background job
		queue_name = (get_environment().get("AI_WHATSAPP_QUEUE") or "long").strip() or "long"
		try:
			custom_timeout = get_environment().get("AI_WHATSAPP_TIMEOUT")
			timeout = int(custom_timeout) if str(custom_timeout or "").strip().isdigit() else 180
		except Exception:
			timeout = 180
		try:
			frappe.enqueue(
				"ai_module.integrations.whatsapp.process_incoming_whatsapp_message",
				queue=queue_name,
				job_name=f"ai_whatsapp_{doc.name}",
				payload=payload,
				now=False,
				timeout=timeout,
			)
		except Exception:
			# Fallback to inline processing if enqueue is unavailable (e.g., local dev)
			try:
				frappe.logger().info("[ai_module] enqueue failed; falling back to inline processing")
			except Exception:
				pass
			process_incoming_whatsapp_message(payload)
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
		# Build a compact, AI-friendly context
		context_summary = {
			"reference": {
				"doctype": payload.get("reference_doctype"),
				"name": payload.get("reference_name"),
			},
			"channel": "whatsapp",
			"lang": None,
			"message": {
				"id": payload.get("message_id"),
				"type": payload.get("message_type"),
				"content_type": payload.get("content_type"),
				"is_reply": payload.get("is_reply"),
				"reply_to": payload.get("reply_to_message_id"),
				"attach": payload.get("attach"),
			},
		}

		# Always use OpenAI Threads: persist a thread per phone number
		phone = (payload.get("from") or "").strip()
		session_id = _get_or_create_thread_for_phone(phone)
		try:
			frappe.logger().info(f"[ai_module] whatsapp session resolved phone={phone} thread={session_id}")
		except Exception:
			pass

		# Attach stored language if available
		try:
			lang_map = _load_lang_map()
			context_summary["lang"] = lang_map.get(phone)
		except Exception:
			pass

		# Import AI runtime directly; no HTTP
		from ai_module import api as ai_api

		# Compose an input that includes the user's text and a compact JSON args block
		composed = message_text or ""
		if not composed:
			# For non-text messages, provide a stub plus metadata
			composed = f"[non-text:{payload.get('content_type')}]"
		# Attach lightweight args for the agent to parse (single JSON object)
		composed = f"{composed}\n\n[args]: {frappe.as_json(context_summary)}"

		# Ensure we have an assistant_id, create if missing
		try:
			from ai_module.agents.assistant_setup import ensure_openai_assistant
			ensure_openai_assistant()
		except Exception:
			pass

		result = ai_api.ai_run_agent(agent_name=agent_name, message=composed, session_id=session_id, model=None)
		try:
			frappe.logger().info(f"[ai_module] whatsapp ai result keys={list(result.keys()) if isinstance(result, dict) else type(result)}")
		except Exception:
			pass

        # Optional auto-reply via CRM; prefer DocType override; default ON in dev when env unset
        raw_autoreply = (env.get("AI_AUTOREPLY") or "").strip().lower()
        try:
            doc_settings = frappe.get_single("AI Assistant Settings")
            if getattr(doc_settings, "use_settings_override", 0):
                autoreply = bool(getattr(doc_settings, "wa_enable_autoreply", 0))
            else:
                autoreply = (_is_dev_env() if raw_autoreply == "" else raw_autoreply in {"1", "true", "yes", "on"})
        except Exception:
            autoreply = (_is_dev_env() if raw_autoreply == "" else raw_autoreply in {"1", "true", "yes", "on"})
		try:
			frappe.logger().info(f"[ai_module] whatsapp autoreply={autoreply} raw='{raw_autoreply}'")
		except Exception:
			pass
		if autoreply:
			reply_text = (result.get("final_output") or "").strip() if isinstance(result, dict) else ""
			try:
				frappe.logger().info(f"[ai_module] whatsapp reply_text_chars={len(reply_text)}")
			except Exception:
				pass
			if reply_text:
				try:
					from crm.api.whatsapp import create_whatsapp_message
                    name = create_whatsapp_message(
						payload.get("reference_doctype"),
						payload.get("reference_name"),
						reply_text,
						payload.get("from"),
						"",
						payload.get("name"),
						"text",
					)
					try:
						frappe.logger().info(f"[ai_module] whatsapp created outbound message name={name}")
					except Exception:
						pass
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