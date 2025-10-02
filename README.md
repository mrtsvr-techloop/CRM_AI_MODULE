### ai-module

Un modulo sviluppato daTechloop che permette l'integrazione di modelli LLM nel environment Frappe

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app ai_module
```

### Configuration (Frappe Cloud / Environment)

Set these keys in the Frappe Cloud Environment (Site Config > Environment):

- OPENAI_API_KEY: your OpenAI (or compatible) API key
- OPENAI_BASE_URL: optional, for Azure or compatible endpoints
- OPENAI_ORG_ID: optional
- OPENAI_PROJECT: optional
- AI_DEFAULT_MODEL: optional, defaults to `gpt-4o-mini`
- AI_SESSION_DB: optional SQLite path for session memory (defaults to sites/<site>/private/files/ai_sessions.db)
- AI_SESSION_MODE: optional, defaults to `openai_threads` (set to `local` to use SDK loop without vendor-side persistence)
- AI_OPENAI_ASSISTANT_ID: required when `AI_SESSION_MODE=openai_threads`
- AI_ASSISTANT_NAME: required to auto-create an Assistant (threads mode)
- AI_ASSISTANT_MODEL: required to auto-create an Assistant (threads mode)
- AI_ASSISTANT_INSTRUCTIONS: ignored; instructions (prompt) are defined in code

No frontend is required. The module applies environment on every request/job automatically.

### What this module does (plain English)

- What it is
  - A backend-only AI module that talks to OpenAI for you, remembers conversations safely, and can “do things” inside your CRM (like create a lead) when the AI decides to.

- How it works
  - You set secrets and basic settings (like model name and assistant name) in the environment. No UI needed.
  - You write the AI’s “brain” (the prompt) in code. That’s the personality and rules it follows.
  - The first time a message comes in, the module auto-creates your AI assistant on OpenAI using:
    - Name and model from the environment
    - Instructions (prompt) and available actions (“tools”) from your code
  - Each person’s chat continues in a private OpenAI “thread,” so the AI remembers context.
  - When the AI needs to perform a CRM action (e.g., create a lead), it calls a “tool.” We map that tool to your real CRM function and run it on your server, then send the result back to the AI.

- Why it’s safe and simple
  - No external HTTP hops between your apps; calls are internal.
  - Secrets stay in environment settings.
  - You control the AI’s behavior (prompt) and what it’s allowed to do (tools) in code.

- How you add new actions
  - Create a small file for each action under `ai_module/ai_module/agents/tools/` that tells the AI “what this action is and what info it needs” (the schema), and point it to the real Python function that does the work.
  - The module auto-loads these files; no extra wiring.

- How other apps use it
  - They send a message to the module and get back the AI’s reply.
  - On the first message, the assistant is created automatically; afterward, it’s reused.
  - If the user keeps chatting, we pass the same thread id so the AI remembers the context.

### Python API (internal)

The module provides a lightweight integration layer on top of the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python):

- Registry for tools and agents
- Session memory (SQLite) based on env
- Convenience runners

Minimal example within another app (e.g. `techloop_crm`):

```python
# in your app's boot or startup
import frappe
from ai_module import api as ai_api

# Register a tool (by dotted path)
ai_api.ai_register_tool("techloop_crm.crm.api.activities.create_activity")

# Create an agent with the tool
ai_api.ai_register_agent(
	name="crm_helper",
	instructions="You are a helpful CRM assistant. Be concise.",
	tool_names=["create_activity"],
)

# Run the agent somewhere in your code
result = ai_api.ai_run_agent("crm_helper", message="Schedule a call with ACME tomorrow 10am", session_id=frappe.session.user)
print(result["final_output"])  # agent's final response
```

Alternatively, build agents directly using the SDK and register them:

```python
from agents import Agent
from ai_module.ai_module.agents import register_agent, register_tool, run_agent_sync

@register_tool
def sum_values(a: int, b: int) -> int:
	return a + b

agent = Agent(
	name="math_bot",
	instructions="Use tools if helpful.",
	tools=[sum_values],
)
register_agent(agent, name="math_bot")

print(run_agent_sync("math_bot", "What is 2+3?", session_id="user_123"))
```

### Tracing and Sessions

- Sessions: enabled when `session_id` is provided and session DB is available.
- Tracing: use the Agents SDK configuration to integrate with providers.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/ai_module
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

unlicense

### WhatsApp → AI auto-reply (no HTTP)

Goal: respond via AI to a WhatsApp message received in the CRM without any HTTP hop between apps.

What happens
- Incoming `WhatsApp Message` (created by your webhook integration or CRM) triggers an AI-side listener.
- The AI module forwards the message to the configured AI agent via Python import, not HTTP.
- Session/thread persistence by sender phone ensures context continuity across messages.
- Optional: the AI’s reply is sent back as an Outgoing `WhatsApp Message` via direct Python call into the CRM (still no HTTP).

Where the logic lives
- Listener hook: `ai_module/ai_module/hooks.py` (`doc_events` → `WhatsApp Message.after_insert`).
- Handler: `ai_module/ai_module/integrations/whatsapp.py`.
  - Filters: only Incoming and non-reaction messages.
  - Builds a structured payload for the AI (text, content_type, attachments, reference doc, etc.).
  - Determines the session strategy from env and persists threads when using OpenAI threads.
  - Invokes `ai_module.api.ai_run_agent(...)` directly.
  - If enabled by env, posts an Outgoing reply using CRM’s `create_whatsapp_message` (Python import; no HTTP).

Environment variables
- `AI_AGENT_NAME` (string): which registered agent to run (default: `crm_ai`).
- `AI_SESSION_MODE` (string): `openai_threads` (default) or `local`.
  - `openai_threads`: the listener maps the sender phone to a persistent OpenAI `thread_id` stored at `sites/<site>/private/files/ai_whatsapp_threads.json`.
  - `local`: the listener uses `session_id = whatsapp:<sender_phone>`.
- `AI_AUTOREPLY` (bool-like): when true (`1/true/yes/on`), the AI’s final output is automatically sent back as an Outgoing WhatsApp message via CRM’s `create_whatsapp_message`.
- Standard OpenAI env (see earlier section): `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_ORG_ID`, `OPENAI_PROJECT`, `AI_OPENAI_ASSISTANT_ID`, `AI_ASSISTANT_NAME`, `AI_ASSISTANT_MODEL`.

Reply mechanism (no duplication)
- The AI module does not duplicate CRM logic. It imports and calls the CRM sender (`crm.api.whatsapp.create_whatsapp_message`) so all validations, realtime updates, and notifications continue to work as before.
- The listener ignores non-Incoming messages, so auto-replies won’t loop back into the AI.

Operational notes
- If your WhatsApp webhook is provided by another app (e.g., `frappe_whatsapp`), keep using it. The AI listener triggers on document insert and remains provider-agnostic.
- Media messages are forwarded to the AI with metadata; if no text is present, a short placeholder like `[non-text:image]` is sent alongside args so agents can reason on context.
- Thread persistence file (`ai_whatsapp_threads.json`) is stored under the site’s private files; it can be safely backed up with the site.
