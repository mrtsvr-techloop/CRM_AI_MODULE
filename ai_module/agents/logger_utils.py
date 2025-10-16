"""Logger utility for AI Module.

Provides resilient logger creation that falls back to console logging
if file permissions are insufficient.
"""

import logging
from typing import Any

import frappe


def get_resilient_logger(module_name: str) -> Any:
	"""Get a logger that works even with permission issues.
	
	Tries to use Frappe's logger system first (which logs to files).
	Falls back to console/stream logging if file permissions fail.
	
	Args:
		module_name: Logger name (e.g., "ai_module.threads")
	
	Returns:
		Logger instance (frappe logger or Python logger)
	
	Examples:
		logger = get_resilient_logger("ai_module.threads")
		logger.info("Processing message...")
	"""
	try:
		# Try Frappe logger (logs to files in sites/<site>/logs/)
		return frappe.logger(module_name)
	except (PermissionError, OSError, IOError) as e:
		# Fallback to console logger if file access fails
		logger = logging.getLogger(module_name)
		
		# Only add handler if not already present
		if not logger.handlers:
			handler = logging.StreamHandler()
			formatter = logging.Formatter(
				'%(asctime)s - %(name)s - %(levelname)s - %(message)s',
				datefmt='%Y-%m-%d %H:%M:%S'
			)
			handler.setFormatter(formatter)
			logger.addHandler(handler)
			logger.setLevel(logging.INFO)
			
			# Log the fallback (only once)
			logger.warning(
				f"Using console logger due to file permission error: {e}. "
				f"Logs will not be saved to file."
			)
		
		return logger

