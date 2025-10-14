# AI WhatsApp Reply Modes

This document explains how WhatsApp → AI → WhatsApp replies are processed in the `ai_module`, and how to configure runtime behavior on Frappe Cloud environments.

## Overview

- Incoming WhatsApp messages create a `WhatsApp Message` (Type: Incoming).
- `ai_module` picks the insert via DocEvent and builds a compact payload for the AI.
- A per-phone OpenAI Threads session is maintained and auto-created on first message.
- The AI run waits until completion, including tool calls.
- If `AI_AUTOREPLY` is enabled and the Assistant produced text, an Outgoing `WhatsApp Message` is created.

### What the module does automatically

- Trusts the thread phone: tools never ask the user for a phone number; phone is injected from thread context.
- Auto-creates a CRM Contact on the first message from a phone; idempotent lookup prevents duplicates.
- Pretty phone formatting for Contact display (e.g., `+39 392 601 2793`) while preserving robust matching.
- Persists detected language per phone and passes it to the Assistant; replies follow the user’s language.
- In development, defaults to inline execution and autoreply when env is unset (no worker needed).
- Robot-head (🤖) reaction before processing to indicate the AI is handling the message.
- Human takeover protection: if a human sends an outgoing message to the phone, AI replies are suppressed for a cooldown window (default 5 minutes).

## Processing Modes

There are two ways to run the AI step:

1) Background Worker (recommended)
- The insert handler enqueues a job to the site’s worker.
- Configure queue and timeout via env:
  - `AI_WHATSAPP_QUEUE` (default: `long`)
  - `AI_WHATSAPP_TIMEOUT` in seconds (default: `180`)
- Pros:
  - Non-blocking for inserts/web requests
  - Scales better; resilient to slow model runs
  - Clear separation of concerns (web vs worker)
- Cons:
  - Requires a worker process to be running

2) Inline Fallback (synchronous)
- Controlled by `AI_WHATSAPP_INLINE`. When true, the handler runs the AI in the insert path (no enqueue).
- Pros:
  - Works without a worker; immediate replies
  - Easier to debug because logs surface in-request
- Cons:
  - Blocks the insert path; risk of HTTP timeouts for slow runs
  - Less scalable under high traffic

## Environment Variables

Set these in Frappe Cloud → Site → Environment:

- Core AI:
  - `OPENAI_API_KEY` (required)
  - `OPENAI_ORG_ID` (optional)
  - `OPENAI_PROJECT` (optional)
  - `OPENAI_BASE_URL` (optional)
  - `AI_ASSISTANT_NAME` (optional)
  - `AI_ASSISTANT_MODEL` (optional)
  - `AI_OPENAI_ASSISTANT_ID` (optional; auto-created if missing and key is configured)

- WhatsApp reply behavior:
  - `AI_AUTOREPLY`: one of `1,true,yes,on` to send automatic replies back to WhatsApp
- `AI_WHATSAPP_QUEUE`: background queue name for jobs (default `default`)
  - `AI_WHATSAPP_TIMEOUT`: background job timeout seconds (default `180`)
  - `AI_WHATSAPP_INLINE`: one of `1,true,yes,on` to run inline when no worker is available
  - `AI_HUMAN_COOLDOWN_SECONDS`: suppress AI replies for N seconds after a human sends an outgoing message (default `300`)
  - `AI_WHATSAPP_TYPING_ACK`: enable/disable immediate reaction/ack (robot) prior to AI processing (default enabled in dev)

Use “Debug Environment” in the `AI Assistant Settings` DocType to inspect effective values (API key presence is masked).

## Assistant and Threads

- Assistant ID resolution order respects the DocType flag `use_settings_override`:
  - If enabled and `assistant_id` is set in the DocType, use that.
  - Else use `AI_OPENAI_ASSISTANT_ID` from env.
  - Else use a persisted file if present.
- Threads are created and persisted per phone number. If a thread does not exist, it is created automatically on first message.
- Language is stored per phone and attached to the AI input context under `args.lang`.

## Tools

- Tool schemas are discovered from `ai_module/agents/tools`.
- Python implementations can be provided via `IMPL_DOTTED_PATH` or `IMPL_FUNC` in each tool module.
- At runtime, if the Assistant requires a tool call and the implementation is not yet registered, the system attempts to auto-register it on-demand.
- The `new_client_lead` tool never asks for a phone number; it receives `phone_from` injected from the thread and sets `mobile_no` internally.

## Troubleshooting

- If no reply appears in WhatsApp:
  - Ensure `AI_AUTOREPLY` is enabled
  - Check Frappe Cloud Logs → Worker (or Web if inline). Search for `[ai_module] whatsapp` entries
  - Verify `OPENAI_API_KEY` presence and an Assistant ID via “Debug Environment”
  - If using workers, confirm at least one worker is running on the site
  - If a human recently sent a message, AI replies are intentionally suppressed until cooldown expires
- If tool calls show `no_implementation_for_*` in OpenAI:
  - Confirm the dotted path for the tool implementation is correct and that the providing app is installed

## Recommended Setup

- Use Background Worker mode (`AI_WHATSAPP_INLINE` not set) with:
  - `AI_WHATSAPP_QUEUE=long`
  - `AI_WHATSAPP_TIMEOUT=180` (or higher based on response latency)
- Keep Inline mode as a temporary fallback when a worker isn’t available.

## Persistence Files (site private)

- Threads map: `private/files/ai_whatsapp_threads.json`
- Language map: `private/files/ai_whatsapp_lang.json`
- Human handoff map: `private/files/ai_whatsapp_handoff.json`
