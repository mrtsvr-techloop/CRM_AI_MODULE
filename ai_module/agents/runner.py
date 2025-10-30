"""Agent runner for executing AI assistants via OpenAI Responses API.

This module provides the main entry points for running AI agents. It handles:
- Agent initialization and bootstrapping
- Session management and conversation continuity
- Model override support
- Direct integration with OpenAI Responses API

Uses the modern Responses API (not deprecated Assistants API) with
previous_response_id for maintaining conversation state across multiple turns.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

import frappe
from agents import Agent

from .bootstrap import initialize
from .logger_utils import get_resilient_logger
from .registry import get_agent as _get_registered_agent


def _log():
	"""Get Frappe logger for runner module."""
	return get_resilient_logger("ai_module.runner")


def _resolve_agent(agent_or_name: Union[str, Agent], model: Optional[str]) -> Agent:
	"""Resolve agent from name or instance and optionally override model.
	
	Args:
		agent_or_name: Either an Agent instance or agent name string
		model: Optional model override (e.g., "gpt-4")
	
	Returns:
		Agent instance (new instance if model overridden to avoid mutation)
	"""
	# Get agent instance
	if isinstance(agent_or_name, Agent):
		agent = agent_or_name
	else:
		agent = _get_registered_agent(agent_or_name)
	
	# Create new agent with overridden model if specified
	if model:
		agent = Agent(
			name=agent.name,
			instructions=getattr(agent, "instructions", None),
			model=model,
			tools=getattr(agent, "tools", None),
			handoffs=getattr(agent, "handoffs", None),
			output_type=getattr(agent, "output_type", None),
		)
	
	return agent


def _run_via_responses_api(input_text: str, session_id: Optional[str]) -> Dict[str, Any]:
	"""Execute agent via hybrid system: Responses API or Assistants API with PDF context.
	
	Routes to appropriate API based on PDF context configuration:
	- If PDF context enabled: Uses Assistants API with file_search for RAG
	- Otherwise: Uses modern Responses API with previous_response_id
	
	Args:
		input_text: The user message to send to the AI
		session_id: Optional session ID for conversation continuity
	
	Returns:
		Dict with final_output, thread_id (session), and model
	"""
	# Check if PDF context is enabled
	try:
		settings = frappe.get_single("AI Assistant Settings")
		use_pdf_context = settings.enable_pdf_context and settings.assistant_id
	except Exception:
		use_pdf_context = False
	
	if use_pdf_context:
		# Use Assistants API with file_search for PDF-based RAG
		from .assistants_api import run_with_assistants_api
		
		_log().info(f"Running with Assistants API (PDF context) session={session_id or '<new>'}")
		
		return run_with_assistants_api(
			message=input_text,
			assistant_id=settings.assistant_id,
			session_id=session_id
		)
	else:
		# Use modern Responses API (default)
		from .threads import run_with_responses_api
		
		_log().info(f"Running with Responses API session={session_id or '<new>'}")
		
		return run_with_responses_api(
			message=input_text,
			session_id=session_id
		)


def run_agent(
	agent_or_name: Union[str, Agent],
	input_text: str,
	session_id: Optional[str] = None,
	model: Optional[str] = None,
	**runner_kwargs: Any,
) -> Dict[str, Any]:
	"""Run an AI agent and return the response with metadata.
	
	This is the main entry point for executing AI agents. It handles:
	- Agent initialization and bootstrapping
	- Input validation
	- OpenAI Threads API execution
	- Response metadata enrichment
	
	Args:
		agent_or_name: Agent instance or registered agent name
		input_text: User message to send to the AI
		session_id: Optional session ID for conversation continuity
		model: Optional model override (e.g., "gpt-4")
		**runner_kwargs: Additional arguments (currently unused, for future extensions)
	
	Returns:
		Dict containing:
		- final_output: The AI's response text
		- thread_id: Session ID for this conversation
		- model: Model used for this response
		- agent_name: Name of the agent that was run
	
	Raises:
		ValueError: If input_text is empty or not a string
	
	Example:
		result = run_agent("crm_ai", "Create a contact for John Doe")
		print(result["final_output"])  # AI's response
		print(result["thread_id"])     # For conversation continuity
	"""
	import os
	
	# Set environment variable to indicate we're in AI tool call mode
	# This prevents log files from being created during tool calls
	os.environ['AI_TOOL_CALL_MODE'] = '1'
	
	try:
		# Initialize agent system (registers tools, etc.)
		initialize()
		
		# Validate input
		if not isinstance(input_text, str) or not input_text.strip():
			raise ValueError("input_text must be a non-empty string")
		
		# Execute via modern Responses API
		output = _run_via_responses_api(input_text, session_id)
		
		# Add agent name to output
		agent_name = agent_or_name.name if isinstance(agent_or_name, Agent) else str(agent_or_name)
		
		return {**output, "agent_name": agent_name}
	
	finally:
		# Clean up environment variable
		if 'AI_TOOL_CALL_MODE' in os.environ:
			del os.environ['AI_TOOL_CALL_MODE']


def run_agent_sync(
	agent_or_name: Union[str, Agent],
	input_text: str,
	session_id: Optional[str] = None,
	model: Optional[str] = None,
	**runner_kwargs: Any,
) -> str:
	"""Run an AI agent and return only the response text.
	
	Convenience wrapper around run_agent() that extracts just the
	final_output string, discarding metadata. Useful when you only
	need the AI's response and don't care about thread IDs, etc.
	
	Args:
		agent_or_name: Agent instance or registered agent name
		input_text: User message to send to the AI
		session_id: Optional session ID for conversation continuity
		model: Optional model override (e.g., "gpt-4")
		**runner_kwargs: Additional arguments (currently unused)
	
	Returns:
		The AI's response text as a string
	
	Raises:
		ValueError: If input_text is empty or not a string
	
	Example:
		response = run_agent_sync("crm_ai", "What is the weather?")
		print(response)  # Just the AI's answer
	"""
	result = run_agent(
		agent_or_name=agent_or_name,
		input_text=input_text,
		session_id=session_id,
		model=model,
		**runner_kwargs,
	)
	return result["final_output"] 