from __future__ import annotations

import frappe
from frappe.model.document import Document


class AIAssistantSettings(Document):
	def validate(self):
		# Ensure non-empty instructions
		self.instructions = (self.instructions or "").strip()
		if not self.instructions:
			raise frappe.ValidationError("Instructions cannot be empty")

	def on_update(self):
		# Upsert the Assistant whenever settings are saved
		from ai_module.agents.assistant_update import upsert_assistant

		upsert_assistant(force=True)


@frappe.whitelist(methods=["POST"])
def ai_assistant_force_update() -> str:
	"""Manual button action to force update of Assistant even without changes."""
	from ai_module.agents.assistant_update import upsert_assistant

	return upsert_assistant(force=True) 