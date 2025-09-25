from __future__ import annotations

from typing import Callable, Dict, List, Optional

from agents import Agent, function_tool


_TOOL_REGISTRY: Dict[str, Callable] = {}
_AGENT_REGISTRY: Dict[str, Agent] = {}


def register_tool(func: Callable, name: Optional[str] = None) -> Callable:
	"""Register a function as a tool and return the wrapped tool.

	- If `name` is provided, it's used as the registry key; otherwise uses func.__name__.
	- The function is decorated with the Agents SDK `@function_tool` so it is compatible
	  with tool-calling.
	"""
	wrapped = function_tool(func)
	key = name or func.__name__
	_TOOL_REGISTRY[key] = wrapped
	return wrapped


def list_tools() -> List[str]:
	return sorted(_TOOL_REGISTRY.keys())


def get_tool(name: str) -> Callable:
	return _TOOL_REGISTRY[name]


def register_agent(agent: Agent, name: Optional[str] = None) -> Agent:
	"""Register an agent under a name. Returns the agent for chaining."""
	key = name or agent.name
	_AGENT_REGISTRY[key] = agent
	return agent


def get_agent(name: str) -> Agent:
	return _AGENT_REGISTRY[name]


def list_agents() -> List[str]:
	return sorted(_AGENT_REGISTRY.keys()) 