"""Agent and tool registry for managing AI assistant components.

This module provides a centralized registry for AI tools and agents,
allowing dynamic registration and retrieval of components used by the
AI assistant system.

Tools are functions that the AI can call to perform actions (e.g., create
contacts, send emails). Agents are AI assistants with specific instructions
and capabilities.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from agents import Agent, function_tool


# Global registries
_TOOL_REGISTRY: Dict[str, Callable] = {}
_AGENT_REGISTRY: Dict[str, Agent] = {}


def register_tool(func: Callable, name: Optional[str] = None) -> Callable:
	"""Register a function as an AI-callable tool.
	
	Wraps the function with @function_tool decorator to make it compatible
	with the AI agent's tool-calling mechanism. The registered tool can then
	be used by AI agents to perform specific actions.
	
	Args:
		func: The function to register as a tool
		name: Optional custom name for the tool (defaults to func.__name__)
	
	Returns:
		The wrapped function tool
	
	Raises:
		ValueError: If func is not callable or name is empty
	
	Example:
		@register_tool
		def create_contact(name: str, email: str):
			# Implementation
			pass
	"""
	if not callable(func):
		raise ValueError("register_tool: func must be callable")
	
	# Use provided name or extract from function
	tool_name = (name or getattr(func, "__name__", "")).strip()
	if not tool_name:
		raise ValueError("register_tool: name cannot be empty")
	
	# Wrap with function_tool decorator and register
	wrapped_tool = function_tool(func)
	_TOOL_REGISTRY[tool_name] = wrapped_tool
	
	return wrapped_tool


def list_tools() -> List[str]:
	"""Get list of all registered tool names.
	
	Returns:
		Sorted list of tool names
	"""
	return sorted(_TOOL_REGISTRY.keys())


def get_tool(name: str) -> Callable:
	"""Retrieve a registered tool by name.
	
	Args:
		name: The tool name to look up
	
	Returns:
		The registered tool function
	
	Raises:
		KeyError: If name is empty or tool not found
	"""
	tool_name = (name or "").strip()
	if not tool_name:
		raise KeyError("get_tool: name cannot be empty")
	
	if tool_name not in _TOOL_REGISTRY:
		raise KeyError(f"Tool not registered: {tool_name}")
	
	return _TOOL_REGISTRY[tool_name]


def register_agent(agent: Agent, name: Optional[str] = None) -> Agent:
	"""Register an AI agent in the global registry.
	
	Allows agents to be retrieved by name for execution. The agent can be
	looked up later using get_agent().
	
	Args:
		agent: The Agent instance to register
		name: Optional custom name (defaults to agent.name)
	
	Returns:
		The agent instance (for chaining)
	
	Raises:
		ValueError: If name is empty
	
	Example:
		agent = Agent(name="crm_ai", instructions="Help with CRM")
		register_agent(agent)
	"""
	# Use provided name or extract from agent
	agent_name = (name or getattr(agent, "name", "")).strip()
	if not agent_name:
		raise ValueError("register_agent: name cannot be empty")
	
	_AGENT_REGISTRY[agent_name] = agent
	return agent


def get_agent(name: str) -> Agent:
	"""Retrieve a registered agent by name.
	
	Args:
		name: The agent name to look up
	
	Returns:
		The registered Agent instance
	
	Raises:
		KeyError: If name is empty or agent not found
	"""
	agent_name = (name or "").strip()
	if not agent_name:
		raise KeyError("get_agent: name cannot be empty")
	
	if agent_name not in _AGENT_REGISTRY:
		raise KeyError(f"Agent not registered: {agent_name}")
	
	return _AGENT_REGISTRY[agent_name]


def list_agents() -> List[str]:
	"""Get list of all registered agent names.
	
	Returns:
		Sorted list of agent names
	"""
	return sorted(_AGENT_REGISTRY.keys()) 