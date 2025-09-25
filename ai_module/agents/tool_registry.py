from __future__ import annotations

from typing import Any, Callable, Dict

_TOOL_IMPLS: Dict[str, Callable[..., Any]] = {}


def register_tool_impl(name: str, func: Callable[..., Any]) -> None:
	"""Register a Python implementation for an Assistant function tool."""
	_TOOL_IMPLS[name] = func


def get_tool_impl(name: str) -> Callable[..., Any]:
	return _TOOL_IMPLS[name]


def list_tool_impls() -> Dict[str, Callable[..., Any]]:
	return dict(_TOOL_IMPLS) 