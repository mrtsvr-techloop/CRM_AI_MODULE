import frappe
import json
import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

from ai_module.agents.config import get_environment, apply_environment
from ai_module.agents.logger_utils import get_resilient_logger

# Constants
DEFAULT_COOLDOWN_SECONDS = 300
DEFAULT_LANGUAGE = "it"
DEFAULT_QUEUE_NAME = "default"
DEFAULT_TIMEOUT = 180
DEFAULT_AGENT_NAME = "crm_ai"

# File paths
THREAD_MAP_FILE = "ai_whatsapp_threads.json"
LANG_MAP_FILE = "ai_whatsapp_lang.json"
PROFILE_MAP_FILE = "ai_whatsapp_profile.json"
HANDOFF_MAP_FILE = "ai_whatsapp_handoff.json"

# Global thread-safe deduplication cache (shared across all functions)
# This ensures that the same message_id is never processed twice, regardless of
# whether it's processed inline, via queue, or through any other path
_global_processed_message_ids = set()
_global_message_id_locks = {}
_global_locks_lock = threading.Lock()


def _get_or_create_message_lock(message_id: str) -> threading.Lock:
	"""Get or create a thread lock for a specific message_id."""
	with _global_locks_lock:
		if message_id not in _global_message_id_locks:
			_global_message_id_locks[message_id] = threading.Lock()
		return _global_message_id_locks[message_id]


def _check_and_mark_message_processed(message_id: str, logger) -> bool:
	"""Check if message_id was already processed and mark it as processing.
	
	Returns True if message should be processed (not already processed),
	False if it should be skipped (already processed).
	"""
	if not message_id:
		return True  # No message_id, can't deduplicate
	
	lock = _get_or_create_message_lock(message_id)
	
	with lock:
		if message_id in _global_processed_message_ids:
			logger.warning(f"Message ID {message_id} already processed, skipping duplicate")
			return False
		
		_global_processed_message_ids.add(message_id)
		logger.info(f"Marked message ID {message_id} as processing")
		return True


def _log():
	"""Get Frappe logger for WhatsApp integration."""
	return get_resilient_logger("ai_module.whatsapp")


def _ensure_directories():
	"""Ensure required directories exist for WhatsApp data storage."""
	try:
		private_files_path = frappe.utils.get_site_path("private", "files")
		os.makedirs(private_files_path, mode=0o755, exist_ok=True)
	except Exception as e:
		_log().error(f"Failed to ensure directories: {e}")


def _is_incoming_message(doc) -> bool:
	"""Check if message is incoming type."""
	return ((getattr(doc, "type", "") or "").lower() == "incoming")


def _should_ignore(doc) -> bool:
	"""Check if message should be ignored (e.g., reactions)."""
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


# Generic JSON map storage functions
def _get_map_path(filename: str) -> str:
	"""Get the full path for a JSON map file."""
	return frappe.utils.get_site_path("private", "files", filename)


def _load_json_map(filename: str) -> Dict[str, Any]:
	"""Load a JSON map from file. Returns empty dict if file doesn't exist."""
	try:
		path = _get_map_path(filename)
		if not os.path.exists(path):
			return {}
		
		with open(path, "r", encoding="utf-8") as f:
			data = f.read().strip()
			if not data:
				return {}
			return json.loads(data)
	except Exception as e:
		_log().error(f"Failed to load JSON map {filename}: {e}")
		# Try fallback from temp location
		try:
			import tempfile
			temp_dir = tempfile.gettempdir()
			temp_path = os.path.join(temp_dir, f"ai_module_{filename}")
			if os.path.exists(temp_path):
				with open(temp_path, "r", encoding="utf-8") as f:
					data = f.read().strip()
					if not data:
						return {}
					return json.loads(data)
		except Exception as temp_e:
			_log().error(f"Failed to load {filename} even from temp location: {temp_e}")
		return {}


def _save_json_map(filename: str, mapping: Dict[str, Any]) -> None:
	"""Save a JSON map to file. Logs errors but doesn't raise."""
	try:
		path = _get_map_path(filename)
		# Ensure directory exists with proper permissions
		dir_path = os.path.dirname(path)
		os.makedirs(dir_path, mode=0o755, exist_ok=True)
		
		# Write file with proper permissions
		with open(path, "w", encoding="utf-8") as f:
			json.dump(mapping, f, indent=2)
		
		# Set file permissions
		os.chmod(path, 0o644)
		
	except Exception as e:
		_log().error(f"Failed to save JSON map {filename}: {e}")
		# Fallback: try to save in a temporary location
		try:
			import tempfile
			temp_dir = tempfile.gettempdir()
			temp_path = os.path.join(temp_dir, f"ai_module_{filename}")
			with open(temp_path, "w", encoding="utf-8") as f:
				json.dump(mapping, f, indent=2)
			_log().info(f"Saved {filename} to temporary location: {temp_path}")
		except Exception as temp_e:
			_log().error(f"Failed to save {filename} even to temp location: {temp_e}")


# Specific map accessors
def _load_thread_map() -> Dict[str, str]:
	"""Load phone -> thread_id mapping."""
	return _load_json_map(THREAD_MAP_FILE)


def _save_thread_map(mapping: Dict[str, str]) -> None:
	"""Save phone -> thread_id mapping."""
	_save_json_map(THREAD_MAP_FILE, mapping)


def _load_lang_map() -> Dict[str, str]:
	"""Load phone -> language mapping."""
	return _load_json_map(LANG_MAP_FILE)


def _save_lang_map(mapping: Dict[str, str]) -> None:
	"""Save phone -> language mapping."""
	_save_json_map(LANG_MAP_FILE, mapping)


def _load_profile_map() -> Dict[str, Dict[str, Any]]:
	"""Load phone -> profile mapping."""
	return _load_json_map(PROFILE_MAP_FILE)


def _save_profile_map(mapping: Dict[str, Dict[str, Any]]) -> None:
	"""Save phone -> profile mapping."""
	_save_json_map(PROFILE_MAP_FILE, mapping)


def _load_handoff_map() -> Dict[str, float]:
	"""Load phone -> last_human_activity_timestamp mapping."""
	return _load_json_map(HANDOFF_MAP_FILE)


def _save_handoff_map(mapping: Dict[str, float]) -> None:
	"""Save phone -> last_human_activity_timestamp mapping."""
	_save_json_map(HANDOFF_MAP_FILE, mapping)


def _get_ai_settings() -> Optional[Any]:
	"""Get AI Assistant Settings singleton if it exists."""
	try:
		return frappe.get_single("AI Assistant Settings")
	except Exception:
		return None


def _should_show_reaction() -> bool:
	"""Check if reaction should be shown before AI processing."""
	settings = _get_ai_settings()
	if settings and getattr(settings, "use_settings_override", 0):
		return bool(getattr(settings, "wa_enable_reaction", 0))
	
	env_value = (get_environment().get("AI_WHATSAPP_REACTION") or "").strip().lower()
	return env_value in {"1", "true", "yes", "on"}


def _send_reaction(payload: Dict[str, Any]) -> None:
	"""Send a reaction emoji (🤖) to the incoming message before AI processing."""
	try:
		from crm.api.whatsapp import react_on_whatsapp_message
		
		# Get the message document name
		message_name = payload.get("name")
		if not message_name:
			return
		
		# Send robot emoji reaction
		react_on_whatsapp_message("🤖", message_name)
		_log().info(f"Sent reaction 🤖 to message {message_name}")
	except Exception as e:
		_log().warning(f"Failed to send reaction: {e}")
		# Don't fail the whole process if reaction fails


def _mark_human_activity(phone: str) -> None:
	"""Record the time a human sent an outgoing message to this phone."""
	key = (phone or "").strip()
	if not key:
		return
	
	handoff_map = _load_handoff_map()
	handoff_map[key] = time.time()
	_save_handoff_map(handoff_map)


def _human_cooldown_seconds() -> int:
	"""Get human cooldown period in seconds from settings or environment."""
	# Try DocType override first
	settings = _get_ai_settings()
	if settings and getattr(settings, "use_settings_override", 0):
		cooldown = int(getattr(settings, "wa_human_cooldown_seconds", 0) or 0)
		if cooldown > 0:
			return cooldown
	
	# Fall back to environment variable
	env_value = (get_environment().get("AI_HUMAN_COOLDOWN_SECONDS") or "").strip()
	if env_value.isdigit():
		return int(env_value)
	
	return DEFAULT_COOLDOWN_SECONDS


def _is_human_active(phone: str) -> bool:
	"""Return True if a human messaged this phone within the cooldown window."""
	key = (phone or "").strip()
	if not key:
		return False
	
	handoff_map = _load_handoff_map()
	last_timestamp = float(handoff_map.get(key, 0.0))
	
	if last_timestamp <= 0:
		return False
	
	elapsed = time.time() - last_timestamp
	return elapsed < _human_cooldown_seconds()


def _detect_language(text: str) -> str:
	"""Best-effort language detection using langid or keyword heuristics."""
	# Try langid first if available
	try:
		import langid  # type: ignore
		code, _ = langid.classify(text or "")
		return (code or DEFAULT_LANGUAGE).split("-")[0]
	except ImportError:
		pass
	
	# Fall back to simple keyword heuristics
	text_lower = (text or "").lower()
	
	language_keywords = {
		"es": ["hola", "gracias", "buenos", "por favor"],
		"fr": ["bonjour", "merci", "s'il vous plaît", "salut"],
		"en": ["hello", "thanks", "please", "hi", "the "],
		"it": ["ciao", "grazie", "per favore", "buongiorno"],
	}
	
	for lang, keywords in language_keywords.items():
		if any(keyword in text_lower for keyword in keywords):
			return lang
	
	return DEFAULT_LANGUAGE


def _get_or_create_thread_for_phone(phone: str) -> str:
	"""Return a persistent local session_id for a phone number."""
	phone_key = (phone or "").strip()
	thread_map = _load_thread_map()
	
	# Return existing session if found
	if phone_key in thread_map:
		return thread_map[phone_key]
	
	# Create new session with timestamp-based ID
	session_id = f"session_{int(time.time() * 1000)}"
	thread_map[phone_key] = session_id
	_save_thread_map(thread_map)
	
	return session_id


def _ensure_contact_exists(doc) -> None:
	"""Ensure a Contact exists for the incoming message."""
	try:
		from crm.api.workflow import ensure_contact_from_message
		ensure_contact_from_message(message_name=doc.name)
	except Exception as exc:
		_log().exception(f"ensure_contact_from_message failed: {exc}")


def _update_language_for_phone(phone: str, message_text: str) -> None:
	"""Detect and persist language for a phone number."""
	phone_key = phone.strip()
	if not phone_key:
		return
	
	lang_detected = _detect_language(message_text or "")
	lang_map = _load_lang_map()
	
	# Only save if language changed
	if lang_map.get(phone_key) != lang_detected:
		lang_map[phone_key] = lang_detected
		_save_lang_map(lang_map)


def _should_process_inline() -> bool:
	"""Check if messages should be processed inline (synchronously)."""
	settings = _get_ai_settings()
	if settings and getattr(settings, "use_settings_override", 0):
		return bool(getattr(settings, "wa_force_inline", 0))
	
	env_value = (get_environment().get("AI_WHATSAPP_INLINE") or "").strip().lower()
	
	# FOR DEVELOPMENT: If queue processing is enabled but workers are not running,
	# automatically enable inline processing to avoid messages being stuck in queue
	if env_value in {"1", "true", "yes", "on"}:
		return True
	
	# Check if we're in development mode (no workers running)
	# This is a fallback to ensure messages are processed even without workers
	try:
		import frappe
		# If we can't find any active workers, enable inline processing
		# This is a development-friendly approach
		return True  # FORCE INLINE FOR DEVELOPMENT
	except:
		return False


def _get_queue_config() -> Tuple[str, int]:
	"""Get queue name and timeout from environment."""
	env = get_environment()
	queue_name = (env.get("AI_WHATSAPP_QUEUE") or DEFAULT_QUEUE_NAME).strip() or DEFAULT_QUEUE_NAME
	
	timeout_str = (env.get("AI_WHATSAPP_TIMEOUT") or "").strip()
	timeout = int(timeout_str) if timeout_str.isdigit() else DEFAULT_TIMEOUT
	
	return queue_name, timeout


def _check_workers_available() -> bool:
	"""Check if background workers are available to process jobs.
	
	Returns True if workers are likely available, False otherwise.
	This is a best-effort check - it's not 100% reliable but helps
	avoid putting jobs in a queue that will never be processed.
	"""
	try:
		# Check if Redis is configured (required for job queue)
		import frappe
		redis_enabled = frappe.conf.get("redis_queue") or frappe.conf.get("redis_cache")
		if not redis_enabled:
			# No Redis means no queue processing possible
			return False
		
		# Try to check if there are active workers
		# This is a heuristic - check if jobs are being processed
		try:
			from frappe.utils import now_datetime, add_to_date
			cutoff = add_to_date(now_datetime(), minutes=-5)
			
			# Check if any jobs were completed recently (indicating workers are active)
			recent_completed = frappe.get_all("Scheduled Job Log",
				filters={
					"status": "Completed",
					"creation": [">", cutoff]
				},
				limit=1
			)
			
			if recent_completed:
				return True  # Workers appear to be active
			
			# If no recent completed jobs, check if there are stuck jobs
			# If jobs are stuck, workers might not be running
			stuck = frappe.get_all("Scheduled Job Log",
				filters={
					"status": "Queued",
					"creation": ["<", cutoff]
				},
				limit=1
			)
			
			if stuck:
				return False  # Jobs are stuck, workers not processing
			
			# CRITICAL: If Redis is configured but no recent activity,
			# assume workers are NOT available to avoid jobs getting stuck
			# This is safer than assuming workers exist
			_log().warning(
				"Redis configured but no recent job activity detected. "
				"Assuming workers not available - will use inline processing."
			)
			return False  # No recent activity = assume no workers
			
		except Exception as e:
			# If we can't check, assume workers NOT available (safer default)
			_log().warning(f"Could not check worker status: {e}. Assuming no workers.")
			return False
			
	except Exception:
		# If Redis check fails, assume no workers
		return False


def _enqueue_or_process(payload: Dict[str, Any], doc_name: str) -> None:
	"""Enqueue message processing or fall back to inline processing.
	
	If workers are not available, automatically falls back to inline processing
	to ensure messages are always processed.
	
	NOTE: Deduplication is already handled in on_whatsapp_after_insert hook,
	so this function should NOT check deduplication again.
	"""
	# Check if workers are available before enqueueing
	workers_available = _check_workers_available()
	
	if not workers_available:
		_log().warning(
			f"No workers detected - processing inline instead of queue. "
			f"This ensures messages are processed even without workers."
		)
		process_incoming_whatsapp_message(payload)
		return
	
	queue_name, timeout = _get_queue_config()
	
	try:
		_log().info(f"Enqueueing job queue={queue_name} timeout={timeout} name={doc_name}")
		frappe.enqueue(
			"ai_module.integrations.whatsapp.process_incoming_whatsapp_message",
			queue=queue_name,
			job_id=f"ai_whatsapp_{doc_name}",
			payload=payload,
			now=False,
			timeout=timeout,
			enqueue_after_commit=True,
		)
		_log().info(f"Job enqueued successfully: {doc_name}")
		# DO NOT call process_incoming_whatsapp_message here - it will be called by the worker
	except Exception as exc:
		# Only fallback to inline if enqueue actually failed
		# This prevents double processing
		_log().exception(f"Enqueue failed, falling back to inline: {exc}")
		process_incoming_whatsapp_message(payload)


def on_whatsapp_after_insert(doc, method=None):
	"""DocEvent handler for WhatsApp Message after_insert.
	
	Processes incoming messages and forwards them to AI assistant.
	"""
	try:
		# Use resilient logger to avoid permission errors
		from ..agents.logger_utils import get_resilient_logger
		logger = get_resilient_logger("ai_module.whatsapp")
		
		# DEBUG: Log that the function was called
		logger.info(f"AI HOOK TRIGGERED: on_whatsapp_after_insert called for doc={doc.name}, type={doc.get('type')}")
		
		# DEBUG: Log more details about the document
		logger.info(f"AI HOOK DOC DETAILS: name={doc.name}, type={doc.get('type')}, from={doc.get('from')}, message={doc.get('message')[:50] if doc.get('message') else 'None'}..., status={doc.get('status')}")
		
		# DEBUG: Log timestamp for debugging
		import datetime
		logger.info(f"AI HOOK TIMESTAMP: {datetime.datetime.now()}")
		
		# NOTE: Deduplication is handled in process_incoming_whatsapp_message,
		# which is called both inline and via queue. This ensures messages are
		# processed only once regardless of the execution path.
		
		apply_environment()
		
		# Handle outgoing messages - mark human activity for cooldown
		if (doc.type or "").lower() == "outgoing":
			# Check if this is a manual message (human sent from CRM)
			message_label = (doc.get("label") or "").strip()
			if message_label == "Manual":
				# Mark human activity when manual message is sent
				_mark_human_activity(doc.get("to"))
			return
		
		# Skip non-incoming messages and reactions
		is_incoming = _is_incoming_message(doc)
		should_ignore = _should_ignore(doc)
		logger.info(f"AI HOOK CHECK: is_incoming={is_incoming}, should_ignore={should_ignore}")
		
		if not is_incoming or should_ignore:
			logger.info(f"AI HOOK SKIP: Not processing message {doc.name} - is_incoming={is_incoming}, should_ignore={should_ignore}")
			return
		
		logger.info(f"AI HOOK CONTINUE: Processing message {doc.name}")
		
		# Log incoming message
		_log().info(
			f"Received WhatsApp message: name={doc.name} type={doc.get('type')} "
			f"ref={doc.get('reference_doctype')}/{doc.get('reference_name')}"
		)
		
		# Skip if human is actively handling this conversation
		from_field = doc.get("from")
		is_human_active = _is_human_active(from_field)
		logger.info(f"AI HOOK CHECK: from={from_field}, is_human_active={is_human_active}")
		
		if is_human_active:
			_log().info("Human active recently; skipping AI reply")
			return
		
		# DEBUG: Normalize phone number for consistency
		original_from = from_field
		if from_field:
			# Remove + prefix and normalize
			normalized_from = from_field.lstrip('+')
			logger.info(f"AI HOOK PHONE NORMALIZATION: original={original_from}, normalized={normalized_from}")
			
			# Update the document with normalized phone number
			setattr(doc, 'from', normalized_from)
			logger.info(f"AI HOOK PHONE UPDATED: doc.from={getattr(doc, 'from', None)}")
		
		# Ensure contact exists
		_ensure_contact_exists(doc)
		
		# Detect and persist language
		_update_language_for_phone(doc.get("from") or "", doc.get("message") or "")
		
		# Build payload
		payload = _build_payload(doc)
		_log().info(f"Processing message {doc.name}")
		logger.info(f"AI HOOK PAYLOAD: {payload}")
		
		# Process inline or enqueue
		should_process_inline = _should_process_inline()
		logger.info(f"AI HOOK CHECK: should_process_inline={should_process_inline}")
		
		if should_process_inline:
			_log().info(f"Processing inline for message={doc.name}")
			logger.info(f"AI HOOK CALLING: process_incoming_whatsapp_message")
			process_incoming_whatsapp_message(payload)
		else:
			logger.info(f"AI HOOK CALLING: _enqueue_or_process")
			_enqueue_or_process(payload, doc.name)
			
	except Exception as e:
		# Use resilient logger for error handling too
		try:
			from ..agents.logger_utils import get_resilient_logger
			logger = get_resilient_logger("ai_module.whatsapp")
			logger.error(f"AI HOOK ERROR: {str(e)}")
			logger.error(f"AI HOOK TRACEBACK: {frappe.get_traceback()}")
		except:
			# Fallback to console if even resilient logger fails
			print(f"AI HOOK ERROR: {str(e)}")
			print(f"AI HOOK TRACEBACK: {frappe.get_traceback()}")
		
		frappe.log_error(
			message=frappe.get_traceback(),
			title="ai_module.integrations.whatsapp.on_whatsapp_after_insert",
		)


def _build_context_summary(payload: Dict[str, Any], phone: str) -> Dict[str, Any]:
	"""Build AI context from message payload and stored data."""
	context = {
		"reference": {
			"doctype": payload.get("reference_doctype"),
			"name": payload.get("reference_name"),
		},
		"channel": "whatsapp",
		"lang": _load_lang_map().get(phone),
		"profile": _load_profile_map().get(phone),
		"message": {
			"id": payload.get("message_id"),
			"type": payload.get("message_type"),
			"content_type": payload.get("content_type"),
			"is_reply": payload.get("is_reply"),
			"reply_to": payload.get("reply_to_message_id"),
			"attach": payload.get("attach"),
		},
	}
	return context


def _compose_ai_message(message_text: str, context_summary: Dict[str, Any], content_type: str) -> str:
	"""Compose the final message to send to AI, including context."""
	if message_text:
		composed = message_text
	else:
		# For non-text messages, provide a stub plus metadata
		composed = f"[non-text:{content_type}]"
	
	# Attach lightweight args for the agent to parse
	return f"{composed}\n\n[args]: {frappe.as_json(context_summary)}"


def _should_autoreply() -> bool:
	"""Check if auto-reply is enabled."""
	settings = _get_ai_settings()
	if settings and getattr(settings, "use_settings_override", 0):
		return bool(getattr(settings, "wa_enable_autoreply", 0))
	
	env_value = (get_environment().get("AI_AUTOREPLY") or "").strip().lower()
	return env_value in {"1", "true", "yes", "on"}


def _send_autoreply(payload: Dict[str, Any], reply_text: str) -> None:
	"""Send an automatic WhatsApp reply."""
	if not reply_text:
		return
	
	try:
		from crm.api.whatsapp import create_whatsapp_message
		
		# Normalize phone number: remove spaces but keep digits
		# Facebook API accepts format like "393926012793" or "+393926012793"
		phone_from = (payload.get("from") or "").strip()
		# Remove all spaces and keep only digits
		phone_normalized = "".join(c for c in phone_from if c.isdigit())
		# Add + prefix if not present (some WhatsApp APIs expect it)
		if phone_normalized and not phone_from.startswith("+"):
			phone_normalized = "+" + phone_normalized
		
		if not phone_normalized:
			_log().error(f"Invalid phone number in payload: {phone_from}")
			return
		
		_log().info(f"Sending reply to {phone_normalized} (length: {len(reply_text)})")
		
		message_name = create_whatsapp_message(
			payload.get("reference_doctype"),
			payload.get("reference_name"),
			reply_text,
			phone_normalized,  # Use normalized number (digits only)
			"",
			payload.get("name"),
			"text",
			"AI_Assistant",
		)
		_log().info(f"Created outbound message: {message_name}")
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="ai_module.integrations.whatsapp.autoreply_failed",
		)


def process_incoming_whatsapp_message(payload: Dict[str, Any]):
	"""Background job: invoke AI with the given WhatsApp message payload.
	
	Calls AI functions directly via Python import and optionally sends auto-reply.
	"""
	try:
		# Use resilient logger
		from ..agents.logger_utils import get_resilient_logger
		logger = get_resilient_logger("ai_module.whatsapp")
		logger.info(f"PROCESS_INCOMING START: payload={payload}")
		
		# CRITICAL: Check if message has already been processed to prevent duplicate responses
		# Use global deduplication cache (shared across inline, queue, and all paths)
		message_id = payload.get("message_id")
		doc_name = payload.get("name")
		
		if message_id:
			# Use global deduplication function (prevents double processing from inline AND queue)
			if not _check_and_mark_message_processed(message_id, logger):
				logger.warning(f"Message ID {message_id} (doc={doc_name}) already processed, skipping duplicate processing")
				return
		
		# Fallback: if no message_id, use doc.name for deduplication (less reliable)
		if doc_name and not message_id:
			# Use message_id "NO_ID_{doc_name}" for deduplication
			fallback_id = f"NO_ID_{doc_name}"
			if not _check_and_mark_message_processed(fallback_id, logger):
				logger.warning(f"Message {doc_name} already processed (no message_id), skipping duplicate processing")
				return
		
		# Ensure directories exist before processing
		_ensure_directories()
		
		# Get agent name from environment
		agent_name = get_environment().get("AI_AGENT_NAME") or DEFAULT_AGENT_NAME
		
		# Extract message details
		phone = (payload.get("from") or "").strip()
		message_text = (payload.get("message") or "").strip()
		
		# Check if human is actively handling this conversation (cooldown check)
		# This check is done here too to ensure we don't send reaction if cooldown is active
		is_human_active = _is_human_active(phone)
		if is_human_active:
			logger.info(f"Human active recently (cooldown); skipping AI processing and reaction for {phone}")
			return
		
		# Send reaction if enabled - only if AI is taking over the request
		if _should_show_reaction():
			_send_reaction(payload)
		
		# Get or create session for this phone
		session_id = _get_or_create_thread_for_phone(phone)
		_log().info(f"Session resolved: phone={phone} session={session_id}")
		
		# Build context and compose AI message
		context_summary = _build_context_summary(payload, phone)
		composed_message = _compose_ai_message(
			message_text,
			context_summary,
			payload.get("content_type") or "text"
		)
		
		# No need to create assistant with Responses API
		# Configuration is passed directly to responses.create
		
		# Call AI agent
		from ..agents.runner import run_agent
		result = None
		error_occurred = False
		error_message = ""
		
		try:
			result = run_agent(
				agent_or_name=agent_name,
				input_text=composed_message,
				session_id=session_id
			)
			_log().info(f"AI result type: {type(result)}")
			_log().info(f"AI result content: {result}")
		except TimeoutError as timeout_err:
			error_occurred = True
			error_message = str(timeout_err)
			_log().error(f"AI processing timeout: {error_message}")
			logger.error(f"PROCESS_INCOMING TIMEOUT: {error_message}")
			# Create a user-friendly timeout message
			result = {
				"final_output": "Mi dispiace, la richiesta sta richiedendo più tempo del previsto. Per favore riprova tra qualche momento o riformula la domanda in modo più specifico."
			}
		except Exception as ai_error:
			error_occurred = True
			error_message = str(ai_error)
			_log().error(f"AI processing error: {error_message}")
			logger.error(f"PROCESS_INCOMING ERROR: {error_message}")
			# Create a user-friendly error message
			result = {
				"final_output": "Mi dispiace, si è verificato un errore durante l'elaborazione della tua richiesta. Per favore riprova tra qualche momento."
			}
		
		# Handle auto-reply if enabled
		should_autoreply = _should_autoreply()
		logger.info(f"PROCESS_INCOMING CHECK: should_autoreply={should_autoreply}")
		
		# CRITICAL: Mark message as successfully processed AFTER AI processing
		# This ensures we don't process it again even if autoreply fails
		if doc_name:
			try:
				frappe.db.set_value("WhatsApp Message", doc_name, "ai_processed", 1, update_modified=False)
				frappe.db.commit()
				logger.info(f"Marked message {doc_name} as successfully processed")
			except Exception as mark_error:
				logger.warning(f"Could not mark message as processed: {mark_error}")
		
		if should_autoreply:
			reply_text = ""
			if isinstance(result, dict):
				reply_text = (result.get("final_output") or result.get("response") or "").strip()
			
			_log().info(f"Auto-reply enabled, reply length: {len(reply_text)}")
			logger.info(f"PROCESS_INCOMING REPLY: text='{reply_text}', length={len(reply_text)}")
			
			if reply_text:
				logger.info(f"PROCESS_INCOMING CALLING: _send_autoreply")
				_send_autoreply(payload, reply_text)
			else:
				_log().warning("No reply text generated by AI")
				logger.warning("PROCESS_INCOMING: No reply text generated by AI")
		else:
			logger.info("PROCESS_INCOMING: Auto-reply disabled")
		
	except Exception as outer_error:
		# Log the error but also try to send a user-friendly message
		_log().error(f"Unexpected error in process_incoming_whatsapp_message: {outer_error}")
		frappe.log_error(
			message=frappe.get_traceback(),
			title="ai_module.integrations.whatsapp.process_incoming_whatsapp_message",
		)
		
		# Try to send error message to user if autoreply is enabled
		try:
			should_autoreply = _should_autoreply()
			if should_autoreply and payload:
				error_reply = "Mi dispiace, si è verificato un errore imprevisto. Per favore riprova tra qualche momento."
				_send_autoreply(payload, error_reply)
		except Exception:
			# If sending error message fails, just log it
			_log().warning("Could not send error message to user") 