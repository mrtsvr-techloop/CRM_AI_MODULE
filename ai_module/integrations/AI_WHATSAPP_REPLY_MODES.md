# AI WhatsApp Reply Modes

This document explains how WhatsApp → AI → WhatsApp replies are processed in the `ai_module`, and how to configure runtime behavior on Frappe Cloud environments.

## Overview

- Incoming WhatsApp messages create a `WhatsApp Message` (Type: Incoming).
- `ai_module` picks the insert via DocEvent and builds a compact payload for the AI.
- A per-phone OpenAI Threads session is maintained and auto-created on first message.
- The AI run waits until completion, including tool calls.
- If `AI_AUTOREPLY` is enabled and the Assistant produced text, an Outgoing `WhatsApp Message` is created.

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
  - `AI_WHATSAPP_QUEUE`: background queue name for jobs (default `long`)
  - `AI_WHATSAPP_TIMEOUT`: background job timeout seconds (default `180`)
  - `AI_WHATSAPP_INLINE`: one of `1,true,yes,on` to run inline when no worker is available

Use “Debug Environment” in the `AI Assistant Settings` DocType to inspect effective values (API key presence is masked).

## Assistant and Threads

- Assistant ID resolution order respects the DocType flag `use_settings_override`:
  - If enabled and `assistant_id` is set in the DocType, use that.
  - Else use `AI_OPENAI_ASSISTANT_ID` from env.
  - Else use a persisted file if present.
- Threads are created and persisted per phone number. If a thread does not exist, it is created automatically on first message.

## Tools

- Tool schemas are discovered from `ai_module/agents/tools`.
- Python implementations can be provided via `IMPL_DOTTED_PATH` or `IMPL_FUNC` in each tool module.
- At runtime, if the Assistant requires a tool call and the implementation is not yet registered, the system attempts to auto-register it on-demand.

## Troubleshooting

- If no reply appears in WhatsApp:
  - Ensure `AI_AUTOREPLY` is enabled
  - Check Frappe Cloud Logs → Worker (or Web if inline). Search for `[ai_module] whatsapp` entries
  - Verify `OPENAI_API_KEY` presence and an Assistant ID via “Debug Environment”
  - If using workers, confirm at least one worker is running on the site
- If tool calls show `no_implementation_for_*` in OpenAI:
  - Confirm the dotted path for the tool implementation is correct and that the providing app is installed

## Recommended Setup

- Use Background Worker mode (`AI_WHATSAPP_INLINE` not set) with:
  - `AI_WHATSAPP_QUEUE=long`
  - `AI_WHATSAPP_TIMEOUT=180` (or higher based on response latency)
- Keep Inline mode as a temporary fallback when a worker isn’t available.
