"""Bootstrap module for AI agent initialization.

This module handles initialization of the AI agent system, including:
- Environment variable setup for OpenAI
- Tool registration for function calling
- Frappe hooks for request/job lifecycle

All initialization is idempotent and can be called multiple times safely.
"""

from __future__ import annotations

import frappe
import os

from .config import apply_environment
from .logger_utils import get_resilient_logger


def _log():
	"""Get Frappe logger for bootstrap module."""
	return get_resilient_logger("ai_module.bootstrap")


def _ensure_whatsapp_directories() -> None:
	"""Ensure WhatsApp data directories exist with proper permissions."""
	try:
		# Get the private files directory path
		private_files_path = frappe.utils.get_site_path("private", "files")
		
		# Create directory with proper permissions
		os.makedirs(private_files_path, mode=0o755, exist_ok=True)
		
		_log().info(f"WhatsApp data directory ensured: {private_files_path}")
	except Exception as exc:
		_log().warning(f"Failed to ensure WhatsApp directories: {exc}")


def _register_tools() -> None:
	"""Register Python tool implementations for AI function calling.
	
	Best-effort registration - fails silently if tools module unavailable.
	This allows the system to work even if tool dependencies aren't installed.
	"""
	try:
		from .assistant_spec import register_tool_impls
		register_tool_impls()
		_log().info("Tool implementations registered successfully")
	except ImportError:
		_log().debug("Tool implementations not available - skipping registration")
	except Exception as exc:
		_log().warning(f"Failed to register tool implementations: {exc}")


def initialize() -> None:
	"""Initialize AI agent system for execution.
	
	Performs:
	1. Apply OpenAI environment variables (API key, org, project, etc.)
	2. Register tool implementations for function calling
	3. Ensure WhatsApp data directories exist
	
	This is idempotent and safe to call multiple times. Designed to be
	lightweight so it can be called per-request or per-job without overhead.
	
	Called by:
	- before_request() hook (for web requests)
	- before_job() hook (for background workers)
	- run_agent() directly before agent execution
	"""
	# Apply OpenAI environment configuration
	apply_environment()
	
	# Ensure WhatsApp directories exist
	_ensure_whatsapp_directories()
	
	# Register tool implementations
	_register_tools()


def before_request() -> None:
	"""Frappe hook: Initialize agent system before each web request.
	
	Ensures environment and tools are ready for any AI operations
	triggered during the request lifecycle.
	"""
	initialize()


def before_job() -> None:
	"""Frappe hook: Initialize agent system before background jobs.
	
	Ensures environment and tools are ready for any AI operations
	triggered during background job execution.
	"""
	initialize() 