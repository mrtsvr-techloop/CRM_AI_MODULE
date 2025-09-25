from __future__ import annotations

# from typing import Optional

# from agents import SQLiteSession

from .config import apply_environment


def initialize() -> None:
	"""Initialize environment for agent runs.

	This is idempotent and safe to call multiple times. We keep it lightweight
	so it can be called per request/job.
	"""
	apply_environment()
	# Best-effort registration of tool implementations (if dependency app is present)
	try:
		from .assistant_spec import register_tool_impls
		register_tool_impls()
	except Exception:
		pass


def before_request() -> None:
	"""Frappe hook: apply environment on each request."""
	initialize()


def before_job() -> None:
	"""Frappe hook: apply environment before background jobs."""
	initialize()

# Custom DB session (local SQLite) intentionally disabled to use vendor-side threads.
# def get_session(session_id: Optional[str]) -> Optional[SQLiteSession]:
# 	"""Create a SQLite-backed session if a DB path is available.
# 
# 	Returns None to disable session persistence when no path is configured.
# 	"""
# 	from .config import get_session_db_path
# 	if not session_id:
# 		return None
# 	db_path = get_session_db_path()
# 	if not db_path:
# 		return None
# 	return SQLiteSession(session_id, db_path) 