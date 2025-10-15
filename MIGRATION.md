# Migration Guide: Assistants API → Responses API

> Guida completa per aggiornare da Assistants API (deprecata) a Responses API (moderna)

## 🎯 Panoramica

Abbiamo migrato dalla vecchia **Assistants API** (deprecata) alla moderna **Responses API** di OpenAI.

### Perché migrare?

- ❌ **Assistants API deprecata** - Verrà rimossa da OpenAI
- ✅ **Responses API moderna** - Supportata attivamente, più semplice
- ✅ **Meno API calls** - 1 chiamata invece di 3 (thread + message + run)
- ✅ **Codice più pulito** - Niente gestione di Assistant objects
- ✅ **Stesso comportamento** - Funzionalità identica per l'utente finale

## 🔄 Cosa è cambiato

### Architettura

| Prima (Assistants API) | Dopo (Responses API) |
|------------------------|----------------------|
| `client.beta.assistants.create()` | ❌ Rimosso - non serve più |
| `threads.messages.create()` | ❌ Rimosso - tutto in `responses.create` |
| `threads.runs.create()` | ❌ Rimosso - tutto in `responses.create` |
| Thread ID per continuità | ✅ `previous_response_id` per continuità |
| Assistant ID persistito | ❌ Rimosso - config per-call |
| `ai_assistant_id.txt` file | ❌ Rimosso - non serve più |

### File rimossi

```bash
# Questi file non esistono più:
ai_module/agents/assistant_setup.py  # ❌ Eliminato
sites/<site>/private/files/ai_assistant_id.txt  # ❌ Non più usato
```

### Funzioni rimosse/modificate

```python
# ❌ RIMOSSO - Non serve più
from ai_module.agents.assistant_setup import ensure_openai_assistant
from ai_module.agents.config import get_openai_assistant_id
from ai_module.agents.config import set_persisted_assistant_id

# ✅ NUOVO - Usa invece
from ai_module.agents.threads import run_with_responses_api
```

### Environment Variables

| Variabile | Prima | Dopo | Note |
|-----------|-------|------|------|
| `AI_OPENAI_ASSISTANT_ID` | ✅ Usato | ❌ Ignorato | Non serve più |
| `AI_SESSION_MODE` | ✅ `openai_threads` | ❌ Rimosso | Sempre Responses API |
| `AI_SESSION_DB` | ✅ SQLite path | ❌ Rimosso | Non serve DB locale |
| Altri (`API_KEY`, model, etc.) | ✅ Usati | ✅ Usati | **Identici** |

## 📦 Migration Steps

### Step 1: Backup

```bash
# Backup del site (precauzione)
bench backup --site your-site

# Backup files persistenza (opzionale)
cp sites/your-site/private/files/ai_whatsapp_*.json /backup/
```

### Step 2: Update Code

```bash
cd apps/ai_module
git pull origin develop  # O il branch con le modifiche
bench migrate
```

### Step 3: Cleanup Environment

Rimuovi variabili deprecate (opzionale):

```bash
# Queste non sono più usate:
# AI_OPENAI_ASSISTANT_ID
# AI_SESSION_MODE
# AI_SESSION_DB
```

**Nota:** Lasciarle non causa problemi, vengono semplicemente ignorate.

### Step 4: Restart

```bash
bench restart
```

### Step 5: Verify

```bash
# Test che l'AI risponda
# Invia un messaggio WhatsApp di test

# Check logs
tail -f logs/frappe.log | grep ai_module
```

**Expected log:**
```
INFO ai_module.whatsapp: Received WhatsApp message: name=...
INFO ai_module.threads: AI request: message_len=45 session=...
INFO ai_module.threads: AI response: text_len=234 session=...
```

## 🔒 Security - Unchanged

**Importante:** La sicurezza del phone mapping è **identica**.

### Prima (Assistants API)

```
Phone → Session → OpenAI Thread ID
           ↓
   OpenAI non vede phone
```

### Dopo (Responses API)

```
Phone → Session → OpenAI Response ID
           ↓
   OpenAI non vede phone
```

**File identici:**
- `ai_whatsapp_threads.json` - Phone → Session (stesso formato)
- `ai_whatsapp_lang.json` - Language mapping (stesso formato)
- `ai_whatsapp_handoff.json` - Human takeover (stesso formato)

**Nuovo file:**
- `ai_whatsapp_responses.json` - Session → Response ID (prima era thread-based)

## 🔧 Code Changes Required

### Se usavi l'API Python interna

#### Prima (deprecato):

```python
# ❌ Questo NON funziona più
from ai_module.agents.assistant_setup import ensure_openai_assistant

assistant_id = ensure_openai_assistant()
# ...
```

#### Dopo (moderno):

```python
# ✅ Usa invece l'API pubblica
from ai_module import api as ai_api

result = ai_api.ai_run_agent(
    agent_name="crm_ai",
    message="Create contact for John",
    session_id="user_123"
)
```

### Se avevi custom tools

**Nessun cambiamento necessario!** ✅

I tool schemas e implementations sono **identici**:

```python
# Questo codice funziona ancora IDENTICO:
SCHEMA = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "...",
        "parameters": {...}
    }
}

IMPL_FUNC = my_implementation
```

## 🎯 Testing Checklist

Dopo la migrazione, verifica:

- [ ] **WhatsApp auto-reply** funziona
- [ ] **Continuità conversazione** - AI ricorda messaggi precedenti
- [ ] **Tool calling** - AI può creare Lead/Contact
- [ ] **Language detection** - Risposte nella lingua giusta
- [ ] **Human takeover** - AI si pausa dopo messaggio umano
- [ ] **Security** - Phone mai esposti in OpenAI logs
- [ ] **Logs visibili** - `tail -f logs/frappe.log | grep ai_module`

## 🆘 Troubleshooting

### Problema: "No API key configured"

**Soluzione:**
```bash
# Verifica API key
bench console
>>> from ai_module.agents.config import get_environment
>>> env = get_environment()
>>> 'OPENAI_API_KEY' in env  # Deve essere True
```

### Problema: "Module has no attribute 'ensure_openai_assistant'"

**Causa:** Codice vecchio che chiama funzione rimossa.

**Soluzione:** Aggiorna il codice chiamante per usare `ai_run_agent()`.

### Problema: Conversazioni non continuano

**Debug:**
```bash
# Verifica response IDs
cat sites/your-site/private/files/ai_whatsapp_responses.json
```

**Expected:**
```json
{
  "session_1729012345678": "resp_abc123xyz"
}
```

**Fix:** Se file vuoto/corrotto, cancellalo (verrà ricreato):
```bash
rm sites/your-site/private/files/ai_whatsapp_responses.json
```

### Problema: "Assistant not found" errors

**Causa:** Riferimenti a vecchio assistant_id.

**Soluzione:** Con Responses API non serve assistant_id. Verifica che:
1. Non ci siano chiamate a `get_openai_assistant_id()`
2. Environment non abbia `AI_OPENAI_ASSISTANT_ID` (viene ignorato comunque)

## 📊 Performance Comparison

### Prima (Assistants API)

```
1. Create Thread        → 1 API call
2. Add Message          → 1 API call
3. Run Assistant        → 1 API call
4. Poll for completion  → N API calls
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 3 + N API calls (latency: ~2-5s)
```

### Dopo (Responses API)

```
1. Create Response      → 1 API call
   ├─ Input + instructions + tools
   ├─ previous_response_id
   └─ Output + new response_id
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 1 API call (latency: ~1-3s)
```

**Miglioramento:** ~40-60% più veloce! 🚀

## 🔍 What's Not Changed

### Identico - Nessun cambiamento

- ✅ **Phone mapping** - File `ai_whatsapp_threads.json` stesso formato
- ✅ **Security model** - Phone mai esposti a OpenAI
- ✅ **Tool sanitization** - `phone_from` injection identico
- ✅ **Language detection** - Stesso algoritmo e file
- ✅ **Human takeover** - Stesso cooldown mechanism
- ✅ **Auto-reply** - Stesso comportamento
- ✅ **Environment config** - API_KEY, model, base_url identici
- ✅ **DocType override** - AI Assistant Settings stesso ruolo
- ✅ **Logging** - Stesso formato log (solo nomi aggiornati)

## 📚 New Documentation

Leggi la documentazione aggiornata:

- [README.md](README.md) - Setup e architettura generale
- [AI_WHATSAPP_REPLY_MODES.md](ai_module/integrations/AI_WHATSAPP_REPLY_MODES.md) - WhatsApp integration dettagliata

## 💡 Benefits Summary

✅ **Future-proof** - Nessun metodo deprecato
✅ **Simpler** - Meno codice, meno complessità
✅ **Faster** - Meno API calls, latency ridotta
✅ **Same security** - Phone protection invariato
✅ **Same UX** - Comportamento utente identico
✅ **Better logs** - Frappe logger consistente
✅ **Cleaner code** - Best practices Python

## 🎉 Conclusion

La migrazione è **backward-compatible** per gli utenti finali:
- Stesse conversazioni
- Stessa sicurezza
- Stesso auto-reply
- Solo API interna modernizzata

**Action Required:** Minimal - solo update code e restart.

**Breaking Changes:** Solo per codice interno che chiamava `ensure_openai_assistant()` direttamente (rarissimo).

---

Per supporto: apri un issue su GitHub o contatta il team Techloop.

