from __future__ import annotations

import frappe
from frappe.model.document import Document

from ai_module.agents.config import get_environment


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

	def validate(self):
		# Ensure non-empty instructions
		self.instructions = (self.instructions or "").strip()
		if not self.instructions:
			raise frappe.ValidationError("Instructions cannot be empty")
		# Always refresh read-only display fields before save
		self._populate_readonly_from_env()

	def onload(self):
		# Populate read-only fields when form loads
		self._populate_readonly_from_env()

	def on_update(self):
		# Upsert the Assistant whenever settings are saved
		from ai_module.agents.assistant_update import upsert_assistant
		upsert_assistant(force=True)


@frappe.whitelist(methods=["POST"])
def ai_assistant_force_update() -> str:
	"""Manual button action to force update of Assistant even without changes."""
	from ai_module.agents.assistant_update import upsert_assistant
	return upsert_assistant(force=True) 