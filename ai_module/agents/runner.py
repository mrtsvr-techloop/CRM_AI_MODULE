from __future__ import annotations

from typing import Any, Dict, Optional, Union

from agents import Agent, Runner

from .bootstrap import initialize
from .config import get_openai_assistant_id
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
	"""Run an agent via OpenAI Assistants Threads and return output and metadata."""
	initialize()
	out = _run_via_openai_threads(input_text, session_id)
	return {**out, "agent_name": (agent_or_name.name if isinstance(agent_or_name, Agent) else str(agent_or_name))}


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