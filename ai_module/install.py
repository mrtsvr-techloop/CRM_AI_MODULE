from __future__ import annotations

import frappe


def after_install():
	"""Ensure an OpenAI Assistant exists for threads mode and persist its id if created."""
	try:
		from .agents.assistant_setup import ensure_openai_assistant

		assistant_id = ensure_openai_assistant()
		if assistant_id:
			frappe.logger().info(f"[ai_module] Assistant ready: {assistant_id}")
	except Exception as exc:
		# Non-fatal: installation continues even if Assistant creation fails
		frappe.logger().warning(f"[ai_module] Failed to ensure Assistant during install: {exc}") 