from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Dict, List, Optional, Tuple

from ..tool_registry import register_tool_impl

# Cache discovered tools to avoid repeated imports
_DISCOVERED: bool = False
_NAME_TO_SCHEMA: Dict[str, Dict[str, Any]] = {}
_NAME_TO_IMPL: Dict[str, str] = {}


def _extract_name_from_schema(schema: Dict[str, Any]) -> Optional[str]:
	try:
		return schema.get("function", {}).get("name")
	except Exception:
		return None


def _load_module(path: str):
	return importlib.import_module(path)


def _discover_tools() -> None:
	global _DISCOVERED
	if _DISCOVERED:
		return
	pkg_name = __name__
	package = importlib.import_module(pkg_name)
	for finder, mod_name, ispkg in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
		if ispkg:
			continue
		try:
			mod = _load_module(mod_name)
			# Fetch schema from SCHEMA or get_tool_schema()
			schema = getattr(mod, "SCHEMA", None)
			if schema is None and hasattr(mod, "get_tool_schema"):
				schema = mod.get_tool_schema()
			if not schema:
				continue
			name = _extract_name_from_schema(schema)
			if not name:
				continue
			_NAME_TO_SCHEMA[name] = schema

			# Discover implementation
			impl_dotted = getattr(mod, "IMPL_DOTTED_PATH", None)
			impl_func = getattr(mod, "IMPL_FUNC", None)
			if isinstance(impl_dotted, str) and impl_dotted:
				_NAME_TO_IMPL[name] = impl_dotted
			elif callable(impl_func):
				# Register immediately
				register_tool_impl(name, impl_func)
			elif hasattr(mod, "register_tool_impl"):
				try:
					mod.register_tool_impl()
				except Exception:
					pass
		except Exception:
			# Ignore broken tool modules
			continue
	_DISCOVERED = True


def get_all_tool_schemas() -> List[Dict[str, Any]]:
	"""Aggregate tool schemas from individual tool modules (auto-discovered)."""
	_discover_tools()
	return list(_NAME_TO_SCHEMA.values())


def get_tool_schema_by_name(tool_name: str) -> Optional[Dict[str, Any]]:
	_discover_tools()
	return _NAME_TO_SCHEMA.get(tool_name)


def register_all_tool_impls() -> None:
	"""Register Python implementations for all known tools.

	If a module exported IMPL_DOTTED_PATH, we import and register it now.
	If a module exported IMPL_FUNC, it was already registered at discovery time.
	"""
	_discover_tools()
	for name, dotted in list(_NAME_TO_IMPL.items()):
		try:
			module_path, func_name = dotted.rsplit(".", 1)
			func = getattr(importlib.import_module(module_path), func_name)
			register_tool_impl(name, func)
		except Exception:
			# Ignore failures for optional tools
			pass 


def ensure_tool_impl_registered(tool_name: str) -> bool:
	"""Ensure a specific tool implementation is registered on-demand.

	Returns True if registered or already present; False otherwise.
	"""
	_discover_tools()
	from ..tool_registry import list_tool_impls, register_tool_impl
	if tool_name in list_tool_impls():
		return True
	try:
		dotted = _NAME_TO_IMPL.get(tool_name)
		if not dotted:
			return False
		module_path, func_name = dotted.rsplit(".", 1)
		func = getattr(importlib.import_module(module_path), func_name)
		register_tool_impl(tool_name, func)
		return True
	except Exception:
		return False