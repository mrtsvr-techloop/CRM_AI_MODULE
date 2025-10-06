from __future__ import annotations

import frappe
from frappe.model.document import Document

from ai_module.agents.config import (
    get_environment,
    get_openai_assistant_id,
    get_default_model,
    get_session_mode,
    get_session_db_path,
)


class AIAssistantSettings(Document):
	def _populate_readonly_from_env(self):
		"""Populate read-only display fields from Frappe Cloud env (frappe.conf.environment) or os.environ.
		These fields are for display only and not used as inputs (prompt comes from instructions).
		"""
		env = get_environment()
		# Prefer frappe.conf.get('AI_ASSISTANT_*') if present
		conf = frappe.conf or {}
		self.assistant_name = conf.get("AI_ASSISTANT_NAME") or env.get("AI_ASSISTANT_NAME") or ""
		self.model = conf.get("AI_ASSISTANT_MODEL") or env.get("AI_ASSISTANT_MODEL") or ""
		self.project = conf.get("OPENAI_PROJECT") or env.get("OPENAI_PROJECT") or ""
		self.org_id = conf.get("OPENAI_ORG_ID") or env.get("OPENAI_ORG_ID") or ""
		self.base_url = conf.get("OPENAI_BASE_URL") or env.get("OPENAI_BASE_URL") or ""
		# Additional env-derived display fields
		self.api_key_present = 1 if (conf.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY")) else 0
		self.assistant_id = get_openai_assistant_id() or ""
		self.default_model = get_default_model() or ""
		self.session_mode = get_session_mode() or ""
		self.session_db = get_session_db_path() or ""

	def validate(self):
		# Normalize instructions but do not hard-fail during install/first run
		self.instructions = (self.instructions or "").strip()
		# Always refresh read-only display fields before save
		self._populate_readonly_from_env()

	def onload(self):
		# Populate read-only fields when form loads
		self._populate_readonly_from_env()

	def on_update(self):
		# Upsert the Assistant whenever settings are saved, but skip during install
		# or when provider credentials are not configured to avoid bricking install.
		if getattr(frappe.flags, "in_install", False):
			return
		env = get_environment()
		if not env.get("OPENAI_API_KEY"):
			return
		from ai_module.agents.assistant_update import upsert_assistant
		upsert_assistant(force=True)


@frappe.whitelist(methods=["GET"])
def ai_assistant_debug_env() -> dict:
	"""Expose the same info as ai_debug_env for this DocType UI."""
	from ai_module.api import ai_debug_env
	return ai_debug_env()


@frappe.whitelist(methods=["POST"])
def ai_assistant_reset_persistence(clear_threads: bool = True) -> dict:
	"""Expose reset persistence to delete saved assistant id and thread map."""
	from ai_module.api import ai_reset_persistence
	return ai_reset_persistence(clear_threads=clear_threads)


@frappe.whitelist(methods=["POST"])
def ai_assistant_force_update() -> str:
	"""Manual button action to force update of Assistant even without changes."""
	from ai_module.agents.assistant_update import upsert_assistant
	return upsert_assistant(force=True) 