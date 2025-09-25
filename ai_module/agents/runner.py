from __future__ import annotations

from typing import Any, Dict, Optional, Union

from agents import Agent, Runner

from .bootstrap import initialize
from .config import get_default_model, get_session_mode, get_openai_assistant_id
from .registry import get_agent as _get_registered_agent


def _resolve_agent(agent_or_name: Union[str, Agent], model: Optional[str]) -> Agent:
	if isinstance(agent_or_name, Agent):
		agent = agent_or_name
	else:
		agent = _get_registered_agent(agent_or_name)
	if model:
		# Reconstruct agent with overridden model to avoid mutating the original
		agent = Agent(
			name=agent.name,
			instructions=getattr(agent, "instructions", None),
			model=model,
			tools=getattr(agent, "tools", None),
			handoffs=getattr(agent, "handoffs", None),
			output_type=getattr(agent, "output_type", None),
		)
	return agent


def _run_via_openai_threads(input_text: str, session_id: Optional[str]) -> Dict[str, Any]:
	from .assistant_setup import ensure_openai_assistant
	from .threads import run_with_openai_threads

	assistant_id = get_openai_assistant_id()
	if not assistant_id:
		assistant_id = ensure_openai_assistant()
	if not assistant_id:
		raise RuntimeError("Could not determine/create AI Assistant ID for openai_threads mode")
	return run_with_openai_threads(message=input_text, session_id=session_id, assistant_id=assistant_id)


def run_agent(
	agent_or_name: Union[str, Agent],
	input_text: str,
	session_id: Optional[str] = None,
	model: Optional[str] = None,
	**runner_kwargs: Any,
) -> Dict[str, Any]:
	"""Run an agent until final output and return a dict with output and metadata.

	In openai_threads mode, we route to OpenAI Assistants Threads and return the last assistant message.
	Otherwise, we use the Agents SDK loop and (now-disabled) local session memory.
	"""
	initialize()
	mode = get_session_mode()
	if mode == "openai_threads":
		out = _run_via_openai_threads(input_text, session_id)
		return {**out, "agent_name": (agent_or_name.name if isinstance(agent_or_name, Agent) else str(agent_or_name))}

	resolved_model = model or get_default_model()
	agent = _resolve_agent(agent_or_name, resolved_model)
	# Local session disabled; run without persistence
	result = Runner.run_sync(agent, input_text, session=None, **runner_kwargs)
	return {
		"final_output": result.final_output,
		"usage": getattr(result, "usage", None),
		"agent_name": agent.name,
		"model": resolved_model,
	}


def run_agent_sync(
	agent_or_name: Union[str, Agent],
	input_text: str,
	session_id: Optional[str] = None,
	model: Optional[str] = None,
	**runner_kwargs: Any,
) -> str:
	"""Convenience wrapper returning only the final output string."""
	return run_agent(
		agent_or_name=agent_or_name,
		input_text=input_text,
		session_id=session_id,
		model=model,
		**runner_kwargs,
	)["final_output"] 