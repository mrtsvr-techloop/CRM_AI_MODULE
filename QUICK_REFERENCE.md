# AI Module - Quick Reference Card

> Tieni questo file aperto mentre lavori! 🚀

---

## 🔥 Comandi Più Usati

### Vedere Log in Tempo Reale

```bash
# WSL/Ubuntu (Frappe Manager)
cd ~/frappe-bench
tail -f sites/NOME_SITO/logs/bench.log | grep ai_module

# Frappe Cloud
Dashboard → Logs → App Logs → Cerca "ai_module"
```

### Trovare Nome Sito

```bash
ls sites/
# oppure
fm list
```

### Console Python

```bash
# Frappe Manager
fm shell --site NOME_SITO

# Bench classico
bench --site NOME_SITO console
```

---

## ✅ Verifica Funzionamento

### Test Conversazione

1. Invia: **"Ciao, mi chiamo Mario"**
2. Invia: **"Come mi chiamo?"**

**Nei log devi vedere:**
```
[ai_module.threads] INFO: Starting new conversation: session=...
[ai_module.threads] INFO: Continuing conversation: session=...  ✅
```

Se vedi "Continuing", **funziona!** 🎉

---

## 📊 Log da Cercare

| Pattern | Significato |
|---------|-------------|
| `Starting new conversation` | Prima conversazione per questo numero |
| `Continuing conversation` | Conversazione continua (✅ BUONO) |
| `Saved response_id` | Response ID salvato correttamente |
| `Executing tools:` | AI sta chiamando una funzione |
| `AI response: text_len=` | Risposta inviata all'utente |

---

## 🐛 Problemi Comuni

### AI non risponde

```bash
# Verifica autoreply attivo
bench --site SITO console
>>> from ai_module.agents.config import get_environment
>>> print(get_environment().get("AI_AUTOREPLY"))
# Deve essere "true"
```

### AI perde contesto (risponde sempre come nuova conversazione)

```bash
# Verifica response_map
bench --site SITO console
>>> import json
>>> from frappe.utils import get_site_path
>>> path = get_site_path("private", "files", "ai_response_map.json")
>>> with open(path) as f: print(json.load(f))
# Deve avere entries per ogni sessione
```

### Reset completo persistenza

```bash
bench --site SITO console
>>> from ai_module.api import ai_reset_persistence
>>> ai_reset_persistence(clear_threads=True)
```

---

## 🗂️ File Importanti

### Mapping Files (sites/SITO/private/files/)

| File | Contiene |
|------|----------|
| `ai_whatsapp_threads.json` | phone → session_id |
| `ai_response_map.json` | session_id → response_id |
| `ai_language_map.json` | phone → lingua rilevata |
| `ai_human_activity.json` | phone → timestamp cooldown |

### Log Files (sites/SITO/logs/)

| File | Scopo |
|------|-------|
| `bench.log` | Log principale (✅ QUESTO) |
| `web.log` | HTTP requests |
| `worker.log` | Background jobs |

---

## ⚙️ Environment Variables

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `OPENAI_API_KEY` | API key OpenAI | **Required** |
| `AI_ASSISTANT_MODEL` | Modello da usare | `gpt-4o-mini` |
| `AI_AUTOREPLY` | Auto-risposta WhatsApp | `false` |
| `AI_WHATSAPP_INLINE` | Elabora inline o queue | `false` |
| `AI_WHATSAPP_TIMEOUT` | Timeout secondi | `120` |

---

## 🔄 Restart Servizi

```bash
# Frappe Manager
fm restart

# Bench classico
bench restart

# Supervisor
supervisorctl restart all
```

---

## 📚 Guide Complete

- **[LOG_GUIDE.md](./LOG_GUIDE.md)** - Visualizzazione log dettagliata
- **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** - Risoluzione problemi
- **[README.md](./README.md)** - Documentazione completa

---

## 💡 Pro Tips

### Due Terminali WSL Simultanei

**Terminale 1:**
```bash
tail -f sites/SITO/logs/bench.log | grep -E "ai_module|whatsapp"
```

**Terminale 2:**
```bash
# Qui esegui comandi, bench console, etc
# Vedrai i log in tempo reale nel Terminale 1!
```

### Salvare Log per Debug

```bash
tail -500 sites/SITO/logs/bench.log | grep ai_module > ~/ai_debug.log
```

### Vedere Conversazioni Attive

```bash
grep "session=" sites/SITO/logs/bench.log | grep -oP "session=\S+" | sort -u
```

---

**Last update:** 2025-01-16  
**Version:** 1.0 (Responses API)

