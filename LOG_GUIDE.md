# Guida Rapida - Visualizzazione Log AI Module

## 🎯 Quick Start

### Locale (WSL/Ubuntu + Frappe Manager)

```bash
# 1. Apri WSL
wsl

# 2. Vai al bench
cd ~/frappe-bench

# 3. Trova nome sito
ls sites/

# 4. Watch logs in tempo reale
tail -f sites/NOME_SITO/logs/bench.log | grep ai_module
```

### Frappe Cloud

1. Accedi a https://frappecloud.com
2. Seleziona il tuo sito
3. Click **"Logs"** → **"App Logs"**
4. Cerca: `ai_module`

---

## 📋 Comandi Essenziali

### Con Frappe Manager (WSL)

```bash
# Log in tempo reale
fm logs --follow

# Log filtrati per AI
fm logs --follow | grep ai_module

# Log di un sito specifico
fm logs --site techloop.local --follow

# Console Python
fm shell --site techloop.local
```

### Con Bench Classico

```bash
# Log in tempo reale
tail -f sites/techloop.local/logs/bench.log

# Solo AI module
tail -f sites/techloop.local/logs/bench.log | grep ai_module

# Solo errori
tail -f sites/techloop.local/logs/bench.log | grep ERROR

# Console Python
bench --site techloop.local console
```

---

## 🔍 Esempi di Log

### ✅ Conversazione Funzionante

```
[ai_module.threads] INFO: Starting new conversation: session=whatsapp_393331234567
[ai_module.threads] DEBUG: Saved response_id for session whatsapp_393331234567: resp_abc123...
[ai_module.threads] INFO: AI response: text_len=142 session=whatsapp_393331234567

[ai_module.threads] INFO: Continuing conversation: session=whatsapp_393331234567 prev_response=resp_abc123...
[ai_module.threads] DEBUG: Saved response_id for session whatsapp_393331234567: resp_def456...
[ai_module.threads] INFO: AI response: text_len=89 session=whatsapp_393331234567
```

**✅ Questo significa che funziona correttamente!**
- Prima conversazione: "Starting new conversation"
- Seconda conversazione: "Continuing conversation" con prev_response

### ❌ Problema: Mancanza di Continuità

```
[ai_module.threads] INFO: Starting new conversation: session=whatsapp_393331234567
[ai_module.threads] INFO: AI response: text_len=142 session=whatsapp_393331234567

[ai_module.threads] INFO: Starting new conversation: session=whatsapp_393331234567  ❌ PROBLEMA!
[ai_module.threads] INFO: AI response: text_len=89 session=whatsapp_393331234567
```

**❌ Se vedi "Starting new conversation" ogni volta:**
- Il `response_id` non viene salvato correttamente
- Verifica i permessi del file `ai_response_map.json`
- Verifica che il fix del bug sia stato applicato

### 🛠️ Tool Execution

```
[ai_module.threads] INFO: Executing tools: update_contact_from_thread
[ai_module.threads] INFO: Tool result: {"success": true, "contact": {...}}
```

---

## 🐛 Debug Avanzato

### Tracciare Una Conversazione Specifica

```bash
# Trova il session_id nei log
tail -200 sites/techloop.local/logs/bench.log | grep "session=" | grep -oP "session=\S+"

# Esempio output: session=whatsapp_393331234567

# Traccia tutta la conversazione
grep "session=whatsapp_393331234567" sites/techloop.local/logs/bench.log
```

### Vedere Tutti i Response IDs Salvati

```bash
# In Python console
bench --site techloop.local console

>>> import json
>>> from frappe.utils import get_site_path
>>> path = get_site_path("private", "files", "ai_response_map.json")
>>> with open(path) as f:
...     print(json.dumps(json.load(f), indent=2))

{
  "whatsapp_393331234567": "resp_abc123def456789..."
}
```

### Contare Messaggi Elaborati

```bash
# Messaggi di oggi
grep "$(date +%Y-%m-%d)" sites/techloop.local/logs/bench.log | grep "AI request" | wc -l

# Conversazioni uniche
grep "Starting new conversation" sites/techloop.local/logs/bench.log | wc -l
```

### Log con Contesto

```bash
# 3 righe prima e dopo ogni match
tail -200 sites/techloop.local/logs/bench.log | grep -B 3 -A 3 "ai_module"

# Solo errori con contesto
tail -500 sites/techloop.local/logs/bench.log | grep -B 5 -A 5 "ERROR.*ai_module"
```

---

## 💡 Tips & Tricks

### 1. Due Terminali Simultanei

**Terminale 1 - Log Watcher:**
```bash
cd ~/frappe-bench
tail -f sites/techloop.local/logs/bench.log | grep -E "ai_module|whatsapp"
```

**Terminale 2 - Azioni:**
```bash
# Invia messaggi WhatsApp o esegui comandi
# Vedrai i log in tempo reale nel Terminale 1
```

### 2. Colori nei Log (opzionale)

```bash
# Installa ccze per colori
sudo apt install ccze

# Log colorati
tail -f sites/techloop.local/logs/bench.log | grep ai_module | ccze -A
```

### 3. Salvare Log in File

```bash
# Salva ultimi 500 log di AI in file
tail -500 sites/techloop.local/logs/bench.log | grep ai_module > ~/ai_debug.log

# Comprimi e condividi
gzip ~/ai_debug.log
# File: ~/ai_debug.log.gz
```

### 4. Watch Real-time File Changes

```bash
# Guarda il file response_map aggiornarsi
watch -n 1 "cat sites/techloop.local/private/files/ai_response_map.json | jq"
```

---

## 🆘 Problema Comune: "Permission Denied"

Se vedi errori di permessi:

```bash
# Verifica owner
ls -la sites/techloop.local/private/files/ai_*.json

# Correggi permessi (se necessario)
sudo chown -R frappe:frappe sites/techloop.local/private/files/
chmod 644 sites/techloop.local/private/files/ai_*.json
```

---

## 📚 File di Log

### Posizioni Standard

**Frappe Bench:**
```
sites/<site-name>/logs/
├── bench.log          # Log principale (✅ QUESTO)
├── web.log           # Request HTTP
├── worker.log        # Background jobs
├── schedule.log      # Scheduled tasks
└── redis_*.log       # Redis
```

**Frappe Cloud:**
- App Logs → Equivalente a `bench.log`
- Web Logs → Request HTTP
- Error Logs → Solo errori critici

---

## 🎓 Imparare dai Log

### Pattern da Cercare

```bash
# 1. Nuova conversazione
"Starting new conversation"

# 2. Continuazione (IMPORTANTE!)
"Continuing conversation"

# 3. Tool execution
"Executing tools:"

# 4. Response salvato
"Saved response_id"

# 5. Messaggio inviato
"AI response: text_len="
```

### Test di Funzionamento

1. Invia: **"Ciao, mi chiamo Mario"**
   - Log: `Starting new conversation`
   
2. Invia: **"Come mi chiamo?"**
   - Log: `Continuing conversation` ✅
   - Risposta: "Ti chiami Mario" ✅

Se vedi entrambi, **il sistema funziona perfettamente!** 🎉

---

## 📞 Link Utili

- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Guida completa problemi
- [README.md](./README.md) - Documentazione architettura
- [MIGRATION.md](./MIGRATION.md) - Migrazione Assistants → Responses API

---

**Ultima modifica:** 2025-01-16  
**Versione:** 1.0

