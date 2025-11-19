"""AI Assistant Settings DocType.

Manages AI assistant configuration including model, instructions, and tools.
With Responses API, settings are used per-request, not stored in a persistent Assistant object.
"""

from __future__ import annotations

from typing import Dict, Any

import frappe
from frappe.model.document import Document

from ai_module.agents.config import get_environment
from ai_module.agents.assistant_spec import DEFAULT_INSTRUCTIONS
from ai_module.agents.assistant_update import get_current_instructions
from ai_module.agents.logger_utils import get_resilient_logger


def _log():
	"""Get logger for AI Assistant Settings."""
	return get_resilient_logger("ai_module.ai_assistant_settings")


class AIAssistantSettings(Document):
	def before_save(self):
		"""Process PDF if changed and create/update Vector Store.
		Also handles updates to instructions/model/name when PDF is active."""
		# Handle PDF context enable/disable or PDF file change
		if self.enable_pdf_context:
			pdf_changed = self.has_value_changed('knowledge_pdf')
			pdf_enabled = self.has_value_changed('enable_pdf_context') and self.enable_pdf_context
			
			if pdf_changed or pdf_enabled:
				if self.knowledge_pdf:
					# PDF changed or PDF context just enabled, setup everything
					self._setup_pdf_context(pdf_changed=pdf_changed)
				else:
					self._cleanup_pdf_context()
			elif self.knowledge_pdf:
				# PDF is active and unchanged, check if we need to update assistant on OpenAI
				if self.assistant_id:
					self._update_openai_assistant_if_needed()
				elif self.knowledge_pdf:
					# PDF exists but no assistant - might have been deleted on OpenAI, recreate
					self._setup_pdf_context(pdf_changed=True)
		elif not self.enable_pdf_context and (self.vector_store_id or self.assistant_id):
			# PDF context disabled, cleanup
			self._cleanup_pdf_context()
	
	def _setup_pdf_context(self, pdf_changed: bool = True):
		"""Setup Vector Store and Assistant for PDF context.
		This creates/updates the OpenAI Assistant with PDF context.
		If assistant already exists and PDF file hasn't changed, it will be updated instead of recreated.
		
		Args:
			pdf_changed: True if PDF file was changed, False otherwise
		"""
		from ai_module.agents.assistants_api import (
			create_vector_store_with_file,
			create_assistant_with_vector_store,
			delete_vector_store,
			delete_assistant,
			update_assistant_on_openai
		)
		from ai_module.agents.assistant_spec import DEFAULT_INSTRUCTIONS
		from ai_module.agents.config import apply_environment
		import os
		
		# Apply environment with current DocType instance (for unsaved API key)
		apply_environment(settings_instance=self)
		
		# Validate PDF file
		file_path = frappe.get_site_path('public', self.knowledge_pdf.lstrip('/'))
		
		if not os.path.exists(file_path):
			frappe.throw(f"PDF file not found: {self.knowledge_pdf}")
		
		# Check file size (max 32MB)
		file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
		if file_size_mb > 32:
			frappe.throw(f"PDF too large: {file_size_mb:.1f}MB (max 32MB)")
		
		# Get assistant name from doctype
		assistant_name = getattr(self, 'assistant_name', None) or "CRM Assistant with Knowledge Base"
		
		# Get instructions and model (use get_current_instructions to apply placeholder replacement)
		# Pass self to use current DocType instance (with unsaved changes)
		instructions = get_current_instructions(settings_instance=self).strip()
		model = self.model or "gpt-4o-mini"
		
		# If assistant already exists and PDF file hasn't changed, just update assistant config
		# This prevents creating duplicate Vector Stores when re-saving with same PDF
		if self.assistant_id and self.vector_store_id and not pdf_changed:
			_log().info(f"PDF unchanged, updating existing assistant {self.assistant_id}")
			updated = update_assistant_on_openai(
				assistant_id=self.assistant_id,
				instructions=instructions,
				model=model,
				name=assistant_name
			)
			if not updated:
				# Assistant might have been deleted on OpenAI, recreate it
				_log().warning(f"Failed to update assistant {self.assistant_id}, recreating...")
				self._recreate_assistant(file_path, file_size_mb, assistant_name, instructions, model)
			else:
				self.pdf_uploaded_at = frappe.utils.now()
				self.pdf_file_size_mb = round(file_size_mb, 2)
				frappe.msgprint(
					f"Assistant updated successfully!<br>"
					f"Assistant: {self.assistant_id}",
					title="Assistant Updated",
					indicator="green"
				)
		else:
			# PDF changed or no assistant exists, create new setup
			self._recreate_assistant(file_path, file_size_mb, assistant_name, instructions, model)
	
	def _recreate_assistant(self, file_path: str, file_size_mb: float, assistant_name: str, instructions: str, model: str):
		"""Recreate Vector Store and Assistant (used when PDF changes or assistant doesn't exist)."""
		from ai_module.agents.assistants_api import (
			create_vector_store_with_file,
			create_assistant_with_vector_store,
			delete_vector_store,
			delete_assistant
		)
		
		# Delete old resources if they exist
		if self.vector_store_id:
			delete_vector_store(self.vector_store_id)
		if self.assistant_id:
			delete_assistant(self.assistant_id)
		
		# Create new Vector Store with PDF
		store_name = f"KB_{frappe.utils.now()}"
		vector_store_id = create_vector_store_with_file(file_path, store_name)
		
		# Create Assistant with file_search
		assistant_id = create_assistant_with_vector_store(
			vector_store_id=vector_store_id,
			instructions=instructions,
			model=model,
			name=assistant_name
		)
		
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
	
	def _update_openai_assistant_if_needed(self):
		"""Update OpenAI Assistant when instructions/model/name change but PDF is unchanged."""
		from ai_module.agents.assistants_api import update_assistant_on_openai
		from ai_module.agents.config import apply_environment
		
		# Apply environment with current DocType instance (for unsaved API key)
		apply_environment(settings_instance=self)
		
		# Check if any relevant field changed
		instructions_changed = self.has_value_changed('instructions') or self.has_value_changed('client_name')
		model_changed = self.has_value_changed('model')
		name_changed = self.has_value_changed('assistant_name')
		
		if not (instructions_changed or model_changed or name_changed):
			return
		
		if not self.assistant_id:
			return
		
		# Get current values (use get_current_instructions to apply placeholder replacement)
		# Pass self to use current DocType instance (with unsaved changes)
		instructions = get_current_instructions(settings_instance=self).strip() if instructions_changed else None
		model = self.model or "gpt-4o-mini" if model_changed else None
		assistant_name = (getattr(self, 'assistant_name', None) or "CRM Assistant with Knowledge Base") if name_changed else None
		
		_log().info(f"Updating OpenAI Assistant {self.assistant_id} due to field changes")
		
		updated = update_assistant_on_openai(
			assistant_id=self.assistant_id,
			instructions=instructions,
			model=model,
			name=assistant_name
		)
		
		if updated:
			frappe.msgprint(
				f"Assistant updated on OpenAI successfully!<br>"
				f"Assistant: {self.assistant_id}",
				title="Assistant Updated",
				indicator="green"
			)
		else:
			# Assistant might have been deleted, but we can't recreate without PDF
			frappe.msgprint(
				f"Warning: Could not update assistant on OpenAI.<br>"
				f"Please re-upload the PDF to recreate the assistant.",
				title="Update Failed",
				indicator="orange"
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
		env = get_environment()
		conf = frappe.conf or {}
		
		if use_settings:
			# When using DocType settings, check if API key is present in DocType
			from ai_module.agents.config import _get_decrypted_api_key
			api_key = _get_decrypted_api_key(settings_instance=self)
			self.api_key_present = 1 if api_key else 0
			# Don't overwrite user-entered values
			return
		
		# When NOT using DocType settings, populate from environment
		self.assistant_name = conf.get("AI_ASSISTANT_NAME") or env.get("AI_ASSISTANT_NAME") or ""
		self.model = conf.get("AI_ASSISTANT_MODEL") or env.get("AI_ASSISTANT_MODEL") or ""
		self.project = conf.get("OPENAI_PROJECT") or env.get("OPENAI_PROJECT") or ""
		self.org_id = conf.get("OPENAI_ORG_ID") or env.get("OPENAI_ORG_ID") or ""
		# Additional env-derived display fields
		self.api_key_present = 1 if (conf.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY")) else 0
		# Removed fields are no longer populated

	def validate(self):
		use_settings = bool(getattr(self, "use_settings_override", 0))
		
		# If override is enabled but model is empty, set default fallback
		if use_settings and not self.get("model"):
			self.model = "gpt-4o-mini"
		
		# If override is enabled but instructions is empty, populate with default prompt
		if use_settings and not self.get("instructions"):
			self.instructions = DEFAULT_INSTRUCTIONS
		
		# Normalize instructions; allow empty and rely on runtime fallback
		self.instructions = (self.instructions or "").strip()
		
		# Set default values for WhatsApp orchestration
		# When use_settings_override is ON, these are the actual values used
		# When use_settings_override is OFF, these are defaults for display only
		if not hasattr(self, "wa_enable_reaction") or self.wa_enable_reaction is None:
			self.wa_enable_reaction = 0  # Default: false
		if not hasattr(self, "wa_enable_autoreply") or self.wa_enable_autoreply is None:
			self.wa_enable_autoreply = 1  # Default: true
		if not hasattr(self, "wa_force_inline") or self.wa_force_inline is None:
			self.wa_force_inline = 0  # Default: false
		if not hasattr(self, "wa_human_cooldown_seconds") or self.wa_human_cooldown_seconds is None:
			self.wa_human_cooldown_seconds = 0  # Default: 0 seconds
		
		# Always refresh display fields before save (no-op if override is on)
		self._populate_readonly_from_env()

	def onload(self):
		# Populate display fields when form loads (no override when using settings)
		self._populate_readonly_from_env()

	def on_update(self):
		# Upsert the Assistant whenever settings are saved, but skip during install
		# or when provider credentials are not configured to avoid bricking install.
		# IMPORTANT: If PDF context is enabled, DO NOT call upsert_assistant()
		# because that handles the local Responses API, not the OpenAI Assistants API.
		if getattr(frappe.flags, "in_install", False):
			return
		env = get_environment()
		if not env.get("OPENAI_API_KEY"):
			return
		
		# If PDF context is active, skip local assistant update
		# The OpenAI Assistant is already managed in before_save()
		if getattr(self, "enable_pdf_context", False):
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
	from ai_module.api import reset_sessions
	return reset_sessions()


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


@frappe.whitelist(methods=["POST"])
def ai_assistant_force_update_openai() -> Dict[str, Any]:
	"""Force update OpenAI Assistant when PDF context is enabled.
	
	This function forces an update of the OpenAI Assistant with current
	settings (instructions, model, name) even if fields haven't changed.
	
	Returns:
		Dict with success status and message
	"""
	settings = frappe.get_single("AI Assistant Settings")
	
	if not settings.enable_pdf_context:
		return {
			"success": False,
			"error": "PDF context is not enabled. Enable it first and upload a PDF."
		}
	
	if not settings.knowledge_pdf:
		return {
			"success": False,
			"error": "No PDF uploaded. Please upload a PDF first."
		}
	
	if not settings.assistant_id:
		return {
			"success": False,
			"error": "No Assistant ID found. Please re-upload the PDF to create the assistant."
		}
	
	try:
		from ai_module.agents.assistants_api import update_assistant_on_openai
		from ai_module.agents.assistant_update import get_current_instructions
		from ai_module.agents.config import apply_environment
		
		# Apply environment with current DocType instance (for API key)
		apply_environment(settings_instance=settings)
		
		# Use get_current_instructions to apply placeholder replacement
		# Pass settings to use current DocType instance
		instructions = get_current_instructions(settings_instance=settings).strip()
		model = settings.model or "gpt-4o-mini"
		assistant_name = getattr(settings, 'assistant_name', None) or "CRM Assistant with Knowledge Base"
		
		_log().info(f"Forcing update of OpenAI Assistant {settings.assistant_id}")
		
		updated = update_assistant_on_openai(
			assistant_id=settings.assistant_id,
			instructions=instructions,
			model=model,
			name=assistant_name
		)
		
		if updated:
			return {
				"success": True,
				"message": f"Assistant {settings.assistant_id} updated successfully on OpenAI",
				"assistant_id": settings.assistant_id,
				"instructions": instructions[:100] + "..." if len(instructions) > 100 else instructions,
				"model": model,
				"name": assistant_name
			}
		else:
			return {
				"success": False,
				"error": f"Failed to update assistant {settings.assistant_id}. It may have been deleted on OpenAI. Please re-upload the PDF."
			}
	except Exception as e:
		_log().exception(f"Error forcing OpenAI assistant update: {e}")
		return {
			"success": False,
			"error": str(e),
			"traceback": frappe.get_traceback()
		}


@frappe.whitelist(methods=["GET"])
def ai_assistant_check_status() -> Dict[str, Any]:
	"""Check current status of AI Assistant configuration.
	
	Returns:
		Dict with current configuration status
	"""
	settings = frappe.get_single("AI Assistant Settings")
	
	return {
		"enable_pdf_context": bool(settings.enable_pdf_context),
		"assistant_id": settings.assistant_id or None,
		"vector_store_id": settings.vector_store_id or None,
		"knowledge_pdf": settings.knowledge_pdf or None,
		"model": settings.model or None,
		"assistant_name": getattr(settings, 'assistant_name', None) or None,
		"instructions_length": len(settings.instructions or ""),
		"using_openai": bool(settings.enable_pdf_context and settings.assistant_id),
		"using_local": not bool(settings.enable_pdf_context and settings.assistant_id)
	} 