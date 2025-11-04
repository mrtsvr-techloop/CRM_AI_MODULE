# AI Module for Frappe

> Modern AI integration module for Frappe using OpenAI Responses API

Un modulo sviluppato da Techloop che permette l'integrazione di modelli LLM nel framework Frappe, utilizzando la moderna **OpenAI Responses API** (non la deprecata Assistants API).

## 🚀 Features

- ✅ **Modern Responses API** - Usa l'API OpenAI più recente, non deprecata
- ✅ **Zero HTTP overhead** - Integrazione diretta Python tra app
- ✅ **Conversation continuity** - Mantiene il contesto tra messaggi con `previous_response_id`
- ✅ **Function calling** - L'AI può chiamare funzioni Python del tuo CRM
- ✅ **Multi-language support** - Rilevamento automatico lingua per conversazioni
- ✅ **Security-first** - Dati sensibili (phone) mai inviati a OpenAI
- ✅ **WhatsApp integration** - Auto-risposta messaggi WhatsApp via CRM
- ✅ **Frappe Cloud ready** - Configurabile via environment variables

## 📦 Installation

Installa l'app usando [bench](https://github.com/frappe/bench):

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/your-repo/ai_module --branch develop
bench install-app ai_module
```

## ⚙️ Configuration

### Opzione 1: Environment Variables (Frappe Cloud)

Imposta queste variabili in **Site Config → Environment**:

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional - OpenAI Configuration
OPENAI_BASE_URL=https://api.openai.com/v1  # Per Azure o endpoint custom
OPENAI_ORG_ID=org-...
OPENAI_PROJECT=proj_...

# Optional - AI Configuration
AI_ASSISTANT_MODEL=gpt-4o-mini  # Default model
AI_ASSISTANT_NAME=CRM Assistant  # Nome assistant per log
AI_INSTRUCTIONS="You are a helpful CRM assistant"  # Istruzioni custom
```

### Opzione 2: AI Assistant Settings DocType

Abilita l'override da UI:

1. Vai a **AI Assistant Settings**
2. Spunta **Use Settings Override**
3. Configura:
   - **API Key** (campo criptato)
   - **Model** (es. `gpt-4o-mini`)
   - **Instructions** (prompt per l'AI)
   - Base URL, Org ID, Project (opzionale)

**Precedenza configurazione:**
```
OS Environment < Frappe Cloud Env < AI Assistant Settings DocType
                                    (quando use_settings_override = 1)
```

## 🏗️ Architecture

### Come funziona (spiegazione semplice)

1. **Nessun Assistant da creare** - Con la Responses API moderna, non serve più creare/gestire oggetti Assistant
2. **Configurazione per-call** - Model, instructions e tools vengono passati ad ogni chiamata
3. **Persistenza conversazioni** - Usa `previous_response_id` per mantenere il contesto
4. **Sicurezza phone mapping** - I numeri di telefono sono mappati localmente a session_id

### Flusso WhatsApp → AI → WhatsApp

```
1. Messaggio WhatsApp ricevuto
   ↓
2. DocEvent trigger (after_insert)
   ↓
3. Mapping sicuro: Phone → Session ID (locale)
   ↓
4. AI Responses API call
   ├─ Input: message + instructions + tools
   ├─ Context: previous_response_id (se esiste)
   └─ Output: risposta + nuovo response_id
   ↓
5. Salvataggio: Session ID → Response ID (per prossimo turno)
   ↓
6. Auto-reply (se abilitato)
   └─ Invio risposta via CRM (Python diretto, no HTTP)
```

### Security - Phone Number Protection

```python
# ✅ SICURO - Il phone non esce mai dal server
Phone: +393331234567
  ↓
File locale: ai_whatsapp_threads.json
  {
    "+393331234567": "session_1729012345678"
  }
  ↓
OpenAI riceve SOLO: session_id
  ↓
OpenAI NON vede MAI il numero di telefono reale
```

## 🛠️ Python API

### Basic Usage

```python
import frappe
from ai_module import api as ai_api

# Run the default agent
result = ai_api.ai_run_agent(
    agent_name="crm_ai",
    message="Create a contact for John Doe, email john@example.com",
    session_id=frappe.session.user  # For conversation continuity
)

print(result["final_output"])  # AI's response
print(result["thread_id"])     # Session ID for next turn
print(result["model"])          # Model used
```

### Custom Agent with Tools

```python
from ai_module.agents import register_tool, register_agent, run_agent_sync
from agents import Agent

# Define a custom tool
@register_tool
def calculate_discount(price: float, percentage: float) -> float:
    """Calculate discount amount."""
    return price * (percentage / 100)

# Create and register agent
agent = Agent(
    name="sales_bot",
    instructions="You help calculate discounts. Be precise.",
    tools=[calculate_discount],
)
register_agent(agent, name="sales_bot")

# Use the agent
response = run_agent_sync(
    "sales_bot",
    "What's 20% discount on $100?",
    session_id="user_123"
)
print(response)  # "$20.00"
```

### Register External Tool

```python
# Register a tool from your CRM app
ai_api.ai_register_tool("techloop_crm.api.activities.create_activity")

# Use it in an agent
ai_api.ai_register_agent(
    name="crm_helper",
    instructions="You help manage CRM activities.",
    tool_names=["create_activity"],
)
```

## 📱 WhatsApp Integration

### How It Works

1. **Messaggio in arrivo** - WhatsApp Message (Incoming) creato nel DB
2. **Hook trigger** - `on_whatsapp_after_insert` in `integrations/whatsapp.py`
3. **Phone mapping** - Phone → Session ID (file JSON locale)
4. **AI processing** - Chiamata Responses API con contesto
5. **Auto-reply** - Risposta inviata via `crm.api.whatsapp.create_whatsapp_message`

### Environment Variables

```bash
# WhatsApp Behavior
AI_AUTOREPLY=true              # Enable auto-reply (default: false)
AI_AGENT_NAME=crm_ai           # Agent to use (default: crm_ai)

# Processing Mode
AI_WHATSAPP_INLINE=false       # false=background job, true=inline (default: false)
AI_WHATSAPP_QUEUE=default      # Queue name (default: default)
AI_WHATSAPP_TIMEOUT=180        # Job timeout in seconds (default: 180)

# Human Handoff
AI_HUMAN_COOLDOWN_SECONDS=300  # Pause AI after human message (default: 300)
```

### DocType Settings Override

Oppure configura via **AI Assistant Settings**:

- ✅ **Enable Autoreply** (`wa_enable_autoreply`)
- ✅ **Force Inline Processing** (`wa_force_inline`)
- ✅ **Human Cooldown Seconds** (`wa_human_cooldown_seconds`)

### Features Automatiche

- ✅ **Language detection** - Rileva e memorizza la lingua dell'utente
- ✅ **Contact auto-creation** - Crea Contact automaticamente per nuovi phone
- ✅ **Human takeover** - Pausa AI se un umano interviene
- ✅ **Security** - Phone number mai esposto a OpenAI
- ✅ **Conversation context** - Mantiene lo storico via `previous_response_id`

## 🔧 Creating Custom Tools

### Step 1: Create Tool File

Crea `ai_module/agents/tools/my_tool.py`:

```python
"""Tool for doing something useful."""

from typing import Dict, Any

def my_tool_impl(param1: str, param2: int) -> Dict[str, Any]:
    """Implementation of my tool.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Dict with success status and result
    """
    # Your implementation here
    result = f"Processed {param1} with {param2}"
    
    return {
        "success": True,
        "result": result
    }


# Tool schema for OpenAI
SCHEMA = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "Does something useful with parameters",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "First parameter"
                },
                "param2": {
                    "type": "integer",
                    "description": "Second parameter"
                }
            },
            "required": ["param1", "param2"]
        }
    }
}

# Implementation reference
IMPL_FUNC = my_tool_impl
```

### Step 2: Auto-loading

Il tool viene caricato automaticamente! Il sistema:
1. Scansiona `agents/tools/*.py`
2. Carica `SCHEMA` per le definizioni
3. Registra `IMPL_FUNC` per le esecuzioni

## 📊 File Persistence

Il modulo salva dati localmente in `sites/<site>/private/files/`:

```
ai_whatsapp_threads.json     # Phone → Session ID mapping
ai_whatsapp_responses.json   # Session → Response ID mapping
ai_whatsapp_lang.json        # Phone → Detected language
ai_whatsapp_handoff.json     # Phone → Last human activity timestamp
ai_whatsapp_profile.json     # Phone → User profile cache
```

**Tutti questi file sono:**
- ✅ Privati (non accessibili da web)
- ✅ Sicuri (no phone numbers in OpenAI)
- ✅ Backuppabili (con il site backup)

## 🔍 Logging and Debugging

Tutti i log usano `frappe.logger()` per visibilità in **bench console**:

```bash
# Durante sviluppo, watch i log:
tail -f logs/frappe.log | grep ai_module

# Oppure in bench start:
bench start
```

Esempio output:

```
INFO ai_module.whatsapp: Received WhatsApp message: name=WHATSAPP-MSG-0001
INFO ai_module.threads: AI request: message_len=45 session=session_1729016216789
INFO ai_module.threads: AI response: text_len=234 session=session_1729016216789
INFO ai_module.whatsapp: Created outbound message: WHATSAPP-MSG-0002
```

## 🔧 AI Diagnostic (Debug Cloud)

**Data**: 16/01/2025  
**Path**: `/ai-diagnostics`

Pagina web per diagnosticare problemi dell'AI Module su Frappe Cloud senza accesso alla console. 

### Cosa fa:
- **Verifica codice deployato** - Controlla se il codice aggiornato è live
- **Controlla API Key** - Verifica configurazione OpenAI
- **Monitora settings** - Stato AutoReply e configurazioni
- **Analizza sessioni** - Conta conversazioni attive
- **Statistiche messaggi** - Messaggi WhatsApp in/out ultimi 24h
- **Errori recenti** - Ultimi errori AI Module (2h)

### Perché serve:
Su Frappe Cloud non hai accesso a `bench console` per vedere i log. Questa pagina ti permette di:
- Capire se il problema è nel codice o nella configurazione
- Vedere se l'AI sta ricevendo messaggi ma non risponde
- Identificare errori specifici senza accesso ai log
- Resetare le sessioni se bloccate

### Come usare:
1. Vai su `https://TUO-SITO.frappe.cloud/ai-diagnostics`
2. Se non loggato, Frappe ti porta al login
3. La pagina mostra lo stato di tutti i componenti
4. Usa "Reset Sessions" se le conversazioni sono bloccate

## 🧪 Development

### Pre-commit Hooks

Usa `pre-commit` per linting automatico:

```bash
cd apps/ai_module
pre-commit install
```

Tools configurati:
- ✅ **ruff** - Python linting
- ✅ **pyupgrade** - Python syntax upgrade
- ✅ **eslint** - JavaScript linting
- ✅ **prettier** - Code formatting

### Running Tests

```bash
# Run all tests
bench --site your-site run-tests --app ai_module

# Run specific test
bench --site your-site run-tests --app ai_module --module ai_module.tests.test_threads
```

## 🏗️ Code Structure

```
ai_module/
├── agents/
│   ├── tools/              # AI function calling tools
│   │   ├── new_client_lead.py
│   │   └── update_contact.py
│   ├── bootstrap.py        # System initialization
│   ├── config.py           # Configuration management
│   ├── registry.py         # Tool/Agent registry
│   ├── runner.py           # Agent execution
│   ├── threads.py          # Responses API implementation
│   ├── assistant_spec.py   # AI instructions and tools
│   └── assistant_update.py # Config retrieval helpers
├── integrations/
│   └── whatsapp.py         # WhatsApp integration
├── api.py                  # Public Python API
├── hooks.py                # Frappe hooks
└── install.py              # Installation hooks
```

## 🆚 Migration from Assistants API

Se stai aggiornando dalla vecchia Assistants API:

### ❌ Rimosso (deprecato)
- `client.beta.assistants.create()`
- `client.beta.assistants.update()`
- `threads.messages.create()`
- `threads.runs.create()`
- File persistence `ai_assistant_id.txt`
- Funzione `ensure_openai_assistant()`

### ✅ Nuovo (Responses API)
- `client.responses.create()` - singola chiamata per tutto
- `previous_response_id` - per continuità conversazione
- Configurazione passata per-call (model, instructions, tools)
- Nessun oggetto Assistant da gestire

### 📝 Stesso Flusso Funzionale
Il **mapping phone → session** è **identico**, quindi:
- ✅ Sicurezza invariata (phone mai esposto)
- ✅ Persistenza conversazioni invariata
- ✅ WhatsApp integration invariata

## 📚 Additional Resources

### Documentazione di Questo Progetto

- **[LOG_GUIDE.md](./LOG_GUIDE.md)** 🔥 - Guida rapida visualizzazione log (WSL + Frappe Cloud)
- **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** - Risoluzione problemi comuni
- **[MIGRATION.md](./MIGRATION.md)** - Migrazione da Assistants API (deprecata)
- **[AI_WHATSAPP_REPLY_MODES.md](./integrations/AI_WHATSAPP_REPLY_MODES.md)** - Dettagli integrazione WhatsApp

### Link Esterni

- [OpenAI Responses API Docs](https://platform.openai.com/docs/api-reference/responses/create)
- [OpenAI Migration Guide](https://platform.openai.com/docs/guides/migrate-to-responses)
- [Frappe Framework Docs](https://frappeframework.com/docs)

## 📄 License

Unlicense - Free to use, modify, and distribute.

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Follow the code style (pre-commit hooks)
4. Write tests for new features
5. Submit a pull request

## 💬 Support

Per supporto:

1. **Consulta le Guide:**
   - 🔥 [LOG_GUIDE.md](./LOG_GUIDE.md) - Come vedere i log
   - 🐛 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Problemi comuni
   - 📱 [AI_WHATSAPP_REPLY_MODES.md](./integrations/AI_WHATSAPP_REPLY_MODES.md) - WhatsApp

2. **Debugging:**
   ```bash
   # Locale (WSL)
   tail -f sites/<site>/logs/bench.log | grep ai_module
   
   # Frappe Cloud
   Dashboard → Logs → App Logs → Cerca "ai_module"
   ```

3. **GitHub Issues:**
   - [Report a bug](https://github.com/your-repo/ai_module/issues)
   - Includi i log per supporto più veloce
