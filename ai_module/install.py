"""Installation hooks for AI Module.

With the modern Responses API, no assistant setup is required at install time.
Configuration (model, instructions, tools) is passed directly to each API call.
"""

from __future__ import annotations

import frappe


def after_install():
	"""Post-installation setup for AI module.
	
	With Responses API, no OpenAI Assistant object needs to be created.
	This hook is kept for future initialization tasks if needed.
	"""
	frappe.logger().info("[ai_module] AI Module installed - using Responses API") 