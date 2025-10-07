from __future__ import annotations

import frappe
from frappe.model.document import Document

from ai_module.agents.config import get_environment


class AIAssistantSettings(Document):
	def _populate_readonly_from_env(self):
		"""Populate display fields from environment unless user chose to use DocType.
		When `use_settings` is enabled, fields remain as user-entered and editable.
		"""
		use_settings = bool(getattr(self, "use_settings", 0))
		if use_settings:
			return
		env = get_environment()
		conf = frappe.conf or {}
		self.assistant_name = conf.get("AI_ASSISTANT_NAME") or env.get("AI_ASSISTANT_NAME") or ""
		self.model = conf.get("AI_ASSISTANT_MODEL") or env.get("AI_ASSISTANT_MODEL") or ""
		self.project = conf.get("OPENAI_PROJECT") or env.get("OPENAI_PROJECT") or ""
		self.org_id = conf.get("OPENAI_ORG_ID") or env.get("OPENAI_ORG_ID") or ""
		self.base_url = conf.get("OPENAI_BASE_URL") or env.get("OPENAI_BASE_URL") or ""

	def validate(self):
		# Ensure non-empty instructions
		self.instructions = (self.instructions or "").strip()
		if not self.instructions:
			raise frappe.ValidationError("Instructions cannot be empty")
		# When user opts-in to DocType configuration, require an API key
		if getattr(self, "use_settings", 0):
			api_key = (self.api_key or "").strip()
			if not api_key:
				raise frappe.ValidationError("OpenAI API Key is required when using DocType configuration")
		# Refresh display fields from env only if not using settings
		self._populate_readonly_from_env()

	def onload(self):
		# Populate display fields when form loads (no override when using settings)
		self._populate_readonly_from_env()

	def on_update(self):
		# Upsert the Assistant whenever settings are saved
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