# AI WhatsApp Reply Modes

> Documentazione completa dell'integrazione WhatsApp → AI → WhatsApp con OpenAI Responses API

## 📋 Overview

Il modulo `ai_module` fornisce un'integrazione completa tra messaggi WhatsApp e AI, con persistenza della conversazione e auto-reply configurabile.

### Flusso Completo

```
1. WhatsApp Message (Incoming) creato nel DB
   ↓
2. DocEvent: after_insert trigger
   ↓
3. Filtri applicati:
   ├─ Solo messaggi Incoming
   ├─ Escluse reactions
   └─ Verifica human cooldown
   ↓
4. Contact auto-creation (se nuovo phone)
   ↓
5. Language detection e persistence
   ↓
6. Phone → Session mapping (sicurezza)
   ↓
7. AI processing (Responses API)
   ├─ Recupero previous_response_id
   ├─ Chiamata responses.create
   └─ Salvataggio nuovo response_id
   ↓
8. Auto-reply (se abilitato)
   └─ create_whatsapp_message (Python diretto)
```

## 🔒 Security - Phone Number Protection

**IMPORTANTE:** I numeri di telefono NON vengono MAI inviati a OpenAI.

### Mapping Locale

```json
// File: private/files/ai_whatsapp_threads.json
{
  "+393331234567": "session_1729012345678",
  "+393479876543": "session_1729012399999"
}
```

### Come Funziona

1. **Messaggio in arrivo** da `+393331234567`
2. **Lookup locale**: Phone → `session_1729012345678`
3. **Invio a OpenAI**: Solo il session_id anonimo
4. **Tool calls**: `phone_from` injected dal session_id (mai dall'utente)
5. **OpenAI** vede solo: `session_1729012345678` (nessun phone)

### Protezione in Tool Calls

```python
# ❌ BLOCCATO - Phone fornito dall'utente
user_input: {"phone": "+39123456789"}  # Ignorato

# ✅ SICURO - Phone dal thread mapping
system_injection: {"phone_from": "+393331234567"}  # Dal mapping locale
```

Il sistema:
- ✅ **Rimuove** tutti i campi `phone`, `mobile`, `mobile_no` dall'input utente
- ✅ **Inietta** `phone_from` dal mapping locale session→phone
- ✅ **Garantisce** che l'AI non possa manipolare i phone numbers

## ⚙️ Processing Modes

### Mode 1: Background Worker (✅ Raccomandato)

**Configurazione:**
```bash
# Non impostare AI_WHATSAPP_INLINE (default: false)
AI_WHATSAPP_QUEUE=default    # Queue name
AI_WHATSAPP_TIMEOUT=180      # Timeout in seconds
```

**Vantaggi:**
- ✅ Non blocca il web request
- ✅ Scalabile sotto carico
- ✅ Resiliente a run AI lunghi
- ✅ Separazione web/worker

**Requisiti:**
- Almeno 1 worker process attivo
- Queue configurata in `common_site_config.json`

**Quando usare:**
- Produzione
- Traffico moderato/alto
- Quando hai workers disponibili

---

### Mode 2: Inline Processing (⚠️ Solo Dev/Fallback)

**Configurazione:**
```bash
AI_WHATSAPP_INLINE=true      # Force inline processing
```

**Vantaggi:**
- ✅ Funziona senza workers
- ✅ Risposte immediate
- ✅ Più facile da debuggare (log in-request)

**Svantaggi:**
- ❌ Blocca l'insert path
- ❌ Rischio timeout HTTP (se AI lento)
- ❌ Non scala sotto carico

**Quando usare:**
- Sviluppo locale senza workers
- Testing/debugging rapido
- Fallback temporaneo

---

### DocType Override

Puoi forzare inline mode da **AI Assistant Settings**:

```
☑ Use Settings Override
☑ Force Inline Processing (wa_force_inline)
```

**Precedenza:** DocType > Environment > Default (false)

## 🌐 Auto-Reply Configuration

### Environment Variable

```bash
# Enable auto-reply
AI_AUTOREPLY=true             # o: 1, yes, on

# Disable auto-reply (default)
# AI_AUTOREPLY non impostato
```

### DocType Override

```
☑ Use Settings Override
☑ Enable Autoreply (wa_enable_autoreply)
```

**Precedenza:** DocType > Environment > Default (false)

### Come Funziona

1. AI processa il messaggio
2. Estrae `final_output` dalla risposta
3. Se `AI_AUTOREPLY=true` e output non vuoto:
   - Chiama `crm.api.whatsapp.create_whatsapp_message()`
   - Messaggio Outgoing creato nel DB
   - Inviato al numero originale
   - **Nessun loop:** Outgoing messages non triggano il listener

## 👤 Human Takeover

### Funzionalità

Quando un **operatore umano** invia un messaggio Outgoing:
1. **Timestamp salvato** in `ai_whatsapp_handoff.json`
2. **AI pausato** per periodo cooldown
3. **Messaggi Incoming** durante cooldown → AI ignorato
4. **Dopo cooldown** → AI riprende normale

### Configurazione

```bash
# Cooldown period (default: 300 seconds = 5 minutes)
AI_HUMAN_COOLDOWN_SECONDS=300
```

**DocType Override:**
```
☑ Use Settings Override
Human Cooldown Seconds: 300  (wa_human_cooldown_seconds)
```

### File Persistence

```json
// File: private/files/ai_whatsapp_handoff.json
{
  "+393331234567": 1729016789.123,  // Ultimo messaggio umano (timestamp)
  "+393479876543": 1729015234.456
}
```

### Esempio Timeline

```
10:00:00 - User: "Ciao"
10:00:05 - AI: "Ciao, come posso aiutarti?"
10:01:00 - User: "Ho un problema"
10:01:05 - Human: "Ti aiuto io" ← Timestamp salvato
10:02:00 - User: "Grazie" ← AI IGNORATO (cooldown attivo)
10:06:05 - (Cooldown scaduto)
10:07:00 - User: "Altra domanda" ← AI riprende
```

## 🌍 Language Detection

### Auto-Detection

Il sistema rileva automaticamente la lingua dal messaggio:

1. **Prova langid** (se disponibile)
2. **Fallback keywords**: `ciao`, `grazie` → it; `hello`, `thanks` → en
3. **Default**: `it` (italiano)

### Persistence

```json
// File: private/files/ai_whatsapp_lang.json
{
  "+393331234567": "it",
  "+393479876543": "en"
}
```

### AI Context

La lingua viene passata all'AI nel contesto:

```json
{
  "lang": "it",
  "message": {
    "content": "..."
  }
}
```

L'AI può usare questa info per rispondere nella lingua giusta.

## 🛠️ Environment Variables Reference

### Core OpenAI

```bash
# Required
OPENAI_API_KEY=sk-...                  # API key (required)

# Optional
OPENAI_BASE_URL=https://api.openai.com/v1   # Custom endpoint
OPENAI_ORG_ID=org-...                        # Organization ID
OPENAI_PROJECT=proj_...                      # Project ID
```

### AI Configuration

```bash
AI_ASSISTANT_MODEL=gpt-4o-mini         # Model to use
AI_ASSISTANT_NAME=CRM Assistant        # Name for logging
AI_INSTRUCTIONS="..."                  # Custom instructions
AI_AGENT_NAME=crm_ai                   # Agent name to execute
```

### WhatsApp Behavior

```bash
# Auto-reply
AI_AUTOREPLY=true                      # Enable/disable auto-reply

# Processing mode
AI_WHATSAPP_INLINE=false               # true=inline, false=background
AI_WHATSAPP_QUEUE=default              # Background queue name
AI_WHATSAPP_TIMEOUT=180                # Job timeout (seconds)

# Human handoff
AI_HUMAN_COOLDOWN_SECONDS=300          # Cooldown after human message
```

### DocType Override

Tutti questi settings possono essere sovrascritti da **AI Assistant Settings** quando:
```
☑ Use Settings Override = Enabled
```

## 🔧 Tools and Function Calling

### Tool Discovery

Il sistema carica automaticamente tools da:
```
ai_module/agents/tools/*.py
```

Ogni file tool deve definire:
```python
# Schema OpenAI
SCHEMA = {
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "What it does",
        "parameters": {...}
    }
}

# Implementation
IMPL_FUNC = my_implementation_function
```

### Security - Phone Injection

**IMPORTANTE:** I tools **NON** ricevono il phone dall'utente.

```python
# In threads.py - _sanitize_tool_args()
def _sanitize_tool_args(args, thread_id):
    # Get trusted phone from thread mapping
    phone = _lookup_phone_from_thread(thread_id)
    if phone:
        args["phone_from"] = phone  # ✅ Injected dal sistema
    
    # Remove ANY user-supplied phone fields
    for key in ["phone", "mobile", "mobile_no"]:
        args.pop(key, None)  # ✅ Rimosso input utente
    
    return args
```

### Available Tools

**new_client_lead:**
- Crea un nuovo Lead nel CRM
- Riceve `phone_from` dal sistema (mai dall'utente)
- Parametri: first_name, last_name, email, organization, notes

**update_contact:**
- Aggiorna dati Contact esistente
- Riceve `phone_from` dal sistema
- Parametri: first_name, last_name, email, organization

## 📊 Persistence Files

Tutti i file sono in `sites/<site>/private/files/`:

| File | Contenuto | Scopo |
|------|-----------|-------|
| `ai_whatsapp_threads.json` | Phone → Session ID | Anonimizzazione phone |
| `ai_whatsapp_responses.json` | Session → Response ID | Continuità conversazione |
| `ai_whatsapp_lang.json` | Phone → Language | Language detection |
| `ai_whatsapp_handoff.json` | Phone → Timestamp | Human takeover |
| `ai_whatsapp_profile.json` | Phone → Profile data | Cache profilo utente |

**Tutti i file sono:**
- ✅ **Privati** (non accessibili da web)
- ✅ **JSON** (human-readable)
- ✅ **Backuppabili** (inclusi nel site backup)
- ✅ **Sicuri** (solo session IDs in OpenAI, mai phone reali)

## 🐛 Troubleshooting

### Nessuna risposta AI

**Checklist:**
1. ✅ `AI_AUTOREPLY` abilitato?
2. ✅ `OPENAI_API_KEY` configurata?
3. ✅ Worker attivo? (se non inline)
4. ✅ Human ha risposto recentemente? (cooldown)
5. ✅ Log: cerca `[ai_module]` in bench console

**Comandi utili:**
```bash
# Watch log in tempo reale
tail -f logs/frappe.log | grep ai_module

# Check worker status
bench doctor

# Test inline mode (bypass worker)
AI_WHATSAPP_INLINE=true bench restart
```

### Tool call fallisce

**Possibili cause:**
1. ❌ Tool implementation non trovata
2. ❌ Parametri mancanti nello schema
3. ❌ CRM app non installata

**Debug:**
```bash
# Check tool registration
bench console
>>> from ai_module.agents.tools import get_all_tool_schemas
>>> get_all_tool_schemas()

# Check implementation
>>> from ai_module.agents.tool_registry import get_tool_impl
>>> get_tool_impl("new_client_lead")
```

### Risposte in lingua sbagliata

**Fix:**
1. Verifica `ai_whatsapp_lang.json` per il phone
2. L'AI ignora `lang` nel contesto? → Aggiungi a instructions:
   ```
   "Always respond in the user's language ({lang})"
   ```
3. Re-send messaggio per trigger detection

## 🎯 Recommended Setup

### Production (con Workers)

```bash
# OpenAI
OPENAI_API_KEY=sk-...
AI_ASSISTANT_MODEL=gpt-4o-mini

# WhatsApp
AI_AUTOREPLY=true
AI_WHATSAPP_QUEUE=default
AI_WHATSAPP_TIMEOUT=180

# Human handoff
AI_HUMAN_COOLDOWN_SECONDS=300
```

**Worker setup:**
```bash
# In common_site_config.json
{
  "background_workers": 1,
  "gunicorn_workers": 2
}
```

### Development (senza Workers)

```bash
# OpenAI
OPENAI_API_KEY=sk-...
AI_ASSISTANT_MODEL=gpt-4o-mini

# WhatsApp
AI_AUTOREPLY=true
AI_WHATSAPP_INLINE=true  # ← Inline per dev locale

# Cooldown più breve per testing
AI_HUMAN_COOLDOWN_SECONDS=60
```

## 📈 Performance Tips

1. **Use Background Workers** - Scala meglio, non blocca web requests
2. **Adjust Timeout** - Aumenta se AI runs sono lunghi (tool chains)
3. **Monitor Queue** - Verifica backlog in Frappe → System Settings
4. **Enable Caching** - Response ID persistence riduce context rebuild

## 🔐 Security Best Practices

1. ✅ **Phone numbers** - Mai in plain text verso OpenAI
2. ✅ **API Keys** - Sempre in environment o DocType criptato
3. ✅ **Tool sanitization** - `phone_from` sempre injected dal sistema
4. ✅ **Human validation** - Cooldown previene AI takeover inappropriato
5. ✅ **Rate limiting** - Implementa se necessario nel CRM layer

## 📚 See Also

- [README.md](../../README.md) - Setup generale e architettura
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [Frappe DocEvent Hooks](https://frappeframework.com/docs/user/en/api/hooks)
