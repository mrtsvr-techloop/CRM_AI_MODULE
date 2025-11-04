"""AI Assistant Settings DocType.

Manages AI assistant configuration including model, instructions, and tools.
With Responses API, settings are used per-request, not stored in a persistent Assistant object.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document

from ai_module.agents.config import get_environment


class AIAssistantSettings(Document):
	def before_save(self):
		"""Process PDF if changed and create/update Vector Store."""
		if self.enable_pdf_context and self.has_value_changed('knowledge_pdf'):
			if self.knowledge_pdf:
				self._setup_pdf_context()
			else:
				self._cleanup_pdf_context()
		elif not self.enable_pdf_context and (self.vector_store_id or self.assistant_id):
			# PDF context disabled, cleanup
			self._cleanup_pdf_context()

	def _setup_pdf_context(self):
		"""Setup Vector Store and Assistant for PDF context."""
		from ai_module.agents.assistants_api import (
			create_vector_store_with_file,
			create_assistant_with_vector_store,
			delete_vector_store,
			delete_assistant
		)
		from ai_module.agents.assistant_spec import DEFAULT_INSTRUCTIONS
		import os
		
		# Validate PDF file
		file_path = frappe.get_site_path('public', self.knowledge_pdf.lstrip('/'))
		
		if not os.path.exists(file_path):
			frappe.throw(f"PDF file not found: {self.knowledge_pdf}")
		
		# Check file size (max 32MB)
		file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
		if file_size_mb > 32:
			frappe.throw(f"PDF too large: {file_size_mb:.1f}MB (max 32MB)")
		
		# Delete old resources if they exist
		if self.vector_store_id:
			delete_vector_store(self.vector_store_id)
		if self.assistant_id:
			delete_assistant(self.assistant_id)
		
		# Create new Vector Store with PDF
		store_name = f"KB_{frappe.utils.now()}"
		vector_store_id = create_vector_store_with_file(file_path, store_name)
		
		# Create Assistant with file_search
		# Instructions are now plain text (Long Text field), no HTML cleaning needed
		# Note: PDF citations (【】) are automatically removed by the response filter
		instructions = (self.instructions or DEFAULT_INSTRUCTIONS).strip()
		model = self.model or "gpt-4o-mini"
		assistant_id = create_assistant_with_vector_store(vector_store_id, instructions, model)
		
		# Save IDs
		self.vector_store_id = vector_store_id
		self.assistant_id = assistant_id
		self.pdf_uploaded_at = frappe.utils.now()
		self.pdf_file_size_mb = round(file_size_mb, 2)
		
		frappe.msgprint(
			f"PDF Knowledge Base configured successfully!<br>"
			f"Vector Store: {vector_store_id}<br>"
			f"Assistant: {assistant_id}",
			title="Knowledge Base Ready",
			indicator="green"
		)

	def _cleanup_pdf_context(self):
		"""Cleanup Vector Store and Assistant when PDF is removed."""
		from ai_module.agents.assistants_api import delete_vector_store, delete_assistant
		
		if self.vector_store_id:
			delete_vector_store(self.vector_store_id)
			self.vector_store_id = None
		
		if self.assistant_id:
			delete_assistant(self.assistant_id)
			self.assistant_id = None
		
		self.pdf_uploaded_at = None
		self.pdf_file_size_mb = None

	def _populate_readonly_from_env(self):
		"""Populate display fields from environment unless user chose to use DocType.
		When `use_settings_override` is enabled, fields remain as user-entered and editable.
		"""
		use_settings = bool(getattr(self, "use_settings_override", 0))
		if use_settings:
			return
		env = get_environment()
		conf = frappe.conf or {}
		self.assistant_name = conf.get("AI_ASSISTANT_NAME") or env.get("AI_ASSISTANT_NAME") or ""
		self.model = conf.get("AI_ASSISTANT_MODEL") or env.get("AI_ASSISTANT_MODEL") or ""
		self.project = conf.get("OPENAI_PROJECT") or env.get("OPENAI_PROJECT") or ""
		self.org_id = conf.get("OPENAI_ORG_ID") or env.get("OPENAI_ORG_ID") or ""
		# Additional env-derived display fields
		self.api_key_present = 1 if (conf.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY")) else 0
		# Removed fields are no longer populated

	def validate(self):
		# Normalize instructions; allow empty and rely on runtime fallback
		self.instructions = (self.instructions or "").strip()
		# Do not enforce API key at save time; runtime will skip actions if missing
		# Note: assistant_id is now used for PDF context (Assistants API with file_search)
		# It's managed by _setup_pdf_context and should not be cleared here
		if not getattr(self, "use_settings_override", 0):
			# When override is OFF, set default values for WhatsApp orchestration
			# These are used as defaults when no environment variable is set
			# Note: These defaults are only for display; actual behavior is controlled by environment
			if not hasattr(self, "wa_enable_reaction") or self.wa_enable_reaction is None:
				self.wa_enable_reaction = 1
			if not hasattr(self, "wa_enable_autoreply") or self.wa_enable_autoreply is None:
				self.wa_enable_autoreply = 1
			if not hasattr(self, "wa_force_inline") or self.wa_force_inline is None:
				self.wa_force_inline = 0
			if not hasattr(self, "wa_human_cooldown_seconds") or self.wa_human_cooldown_seconds is None:
				self.wa_human_cooldown_seconds = 300
		# Always refresh display fields before save (no-op if override is on)
		self._populate_readonly_from_env()

	def onload(self):
		# Populate display fields when form loads (no override when using settings)
		self._populate_readonly_from_env()

	def on_update(self):
		# Upsert the Assistant whenever settings are saved, but skip during install
		# or when provider credentials are not configured to avoid bricking install.
		if getattr(frappe.flags, "in_install", False):
			return
		env = get_environment()
		if not env.get("OPENAI_API_KEY"):
			return
		# If user opted into using settings as source, force upsert (create if missing)
		# Otherwise, do NOT block save; assistant id will be resolved from env/persisted file
		if not getattr(self, "use_settings_override", 0):
			return
		from ai_module.agents.assistant_update import upsert_assistant
		upsert_assistant(force=True)

	def on_trash(self):
		"""Delete OpenAI resources when settings are deleted."""
		if self.enable_pdf_context:
			self._cleanup_pdf_context()


@frappe.whitelist(methods=["GET", "POST"])
def ai_assistant_debug_env() -> dict:
	"""Expose the same info as ai_debug_env for this DocType UI."""
	from ai_module.api import ai_debug_env
	return ai_debug_env()


@frappe.whitelist(methods=["POST"])
def ai_assistant_reset_persistence(clear_threads: bool = True) -> dict:
	"""Delete persisted session maps (phone->session, session->response).
	
	Args:
		clear_threads: If True, clear all session mappings
	
	Returns:
		{"success": bool, "deleted": {...}}
	"""
	from ai_module.api import ai_reset_persistence
	return ai_reset_persistence(clear_threads=clear_threads)


@frappe.whitelist(methods=["POST"])
def ai_assistant_force_update() -> str:
	"""Validate current assistant configuration.
	
	Returns:
		Validation message string
	
	Note: With Responses API, this validates configuration instead of
	updating a persistent Assistant object.
	"""
	from ai_module.agents.assistant_update import upsert_assistant
	return upsert_assistant(force=True) 