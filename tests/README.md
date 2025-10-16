# AI Module - Test Suite

Test diagnostici per verificare lo stato e il funzionamento del sistema AI.

---

## 🎯 Quick Start

### Test Completo Sistema

```bash
bench console
```

```python
exec(open('apps/ai_module/tests/test_system_health.py').read())
```

### Test Tool Calling

```bash
bench console
```

```python
exec(open('apps/ai_module/tests/test_tool_calling.py').read())
```

---

## 📋 Test Disponibili

### 1. **test_system_health.py** - Health Check Completo

Verifica:
- ✅ Connessione OpenAI
- ✅ Configurazione AI Assistant
- ✅ File sessioni WhatsApp
- ✅ Errori recenti
- ✅ Messaggi WhatsApp
- ✅ Lead creati (tool execution)

**Output atteso:**
```
🎯 Risultato: 6/6 test passati
🎉 Sistema funzionante correttamente!
```

### 2. **test_tool_calling.py** - Test Tool Calling

Verifica il funzionamento del tool calling con la Responses API:
- ✅ Prima chiamata genera tool_call
- ✅ Seconda chiamata con tool result funziona
- ✅ Continuità conversazione funziona
- ❌ Metodo sbagliato genera errore atteso

**Output atteso:**
```
✅ TOOL CALLING VERIFICATO E FUNZIONANTE
```

---

## 🐛 Troubleshooting

### Errore: "No tool output found"

**Causa**: Stai usando `previous_response_id` nel tool calling loop

**Soluzione**: Vedi `RESPONSES_API_TOOL_CALLING.md`

### Errore: "Invalid value: 'tool'"

**Causa**: Stai usando `role: "tool"` per i tool results

**Soluzione**: Usa `role: "user"` invece

### Errore: "OPENAI_API_KEY not configured"

**Causa**: API Key non impostata

**Soluzione**:
1. Vai in **AI Assistant Settings**
2. Abilita "Use Settings Override"
3. Inserisci OpenAI API Key
4. Salva

### Messaggi ricevuti ma nessuna risposta

**Possibili cause:**
1. AutoReply disabilitato → Abilita in AI Assistant Settings
2. Human handoff attivo → Reset handoff file
3. Errori API → Vedi Error Log

**Reset handoff:**
```bash
echo '{}' > sites/site.localhost/private/files/ai_whatsapp_handoffjson
```

---

## 🔧 Reset Completo Sessioni

Se hai problemi di continuità:

```bash
cd /workspace/frappe-bench

echo '{}' > sites/site.localhost/private/files/ai_whatsapp_responses.json
echo '{}' > sites/site.localhost/private/files/ai_whatsapp_threads.json
echo '{}' > sites/site.localhost/private/files/ai_whatsapp_lang.json
echo '{}' > sites/site.localhost/private/files/ai_whatsapp_handoffjson

bench restart
```

---

## 📚 Documentazione

- **RESPONSES_API_TOOL_CALLING.md**: Guida completa tool calling
- **README.md**: Documentazione generale AI Module
- **TROUBLESHOOTING.md**: Guida risoluzione problemi

---

## ✅ Workflow Test Consigliato

### Prima del Deploy

```bash
# 1. Test tool calling
bench console
>>> exec(open('apps/ai_module/tests/test_tool_calling.py').read())

# Se passa, procedi
```

### Dopo il Deploy

```bash
# 1. Health check
bench console
>>> exec(open('apps/ai_module/tests/test_system_health.py').read())

# 2. Test WhatsApp reale
# Invia: "Ciao!"
# Aspetta risposta
# Invia: "Aggiungimi: Test User, test@test.com, Test Corp"

# 3. Verifica lead creato
>>> leads = frappe.get_all("CRM Lead", filters={"email": "test@test.com"}, limit=1)
>>> print(leads)
```

---

## 🎯 Interpretazione Risultati

### Tutti i Test Passati ✅
Sistema funzionante correttamente!

### Test OpenAI Connection Failed ❌
- Verifica API Key
- Controlla connessione internet
- Verifica firewall

### Test Recent Errors Failed ⚠️
- Vedi Error Log per dettagli
- Errori comuni:
  - `BadRequestError`: Problema formato API
  - `ValidationError`: Problema dati
  - `PermissionError`: Problema permessi file

### Test Leads Created Failed ❌
- Tool non viene eseguito
- Verifica tool registration
- Vedi `RESPONSES_API_TOOL_CALLING.md`

---

**Ultimo aggiornamento**: 2025-10-16

