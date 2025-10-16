# AI Module - Troubleshooting Guide

## Bug Fix: AI Risponde Solo Una Volta

### 🐛 Problema Risolto
Il sistema rispondeva solo al primo messaggio e poi si bloccava, perdendo la continuità della conversazione.

### ✅ Causa Identificata
Nel loop di iterazione della Responses API, la variabile `prev_id` (previous_response_id) non veniva aggiornata dopo ogni risposta. Questo causava la perdita del contesto tra i turni di conversazione.

### 🔧 Fix Applicato
Aggiornato `threads.py` per:
1. Aggiornare `prev_id` dopo ogni risposta OpenAI
2. Salvare il nuovo `response_id` nel mapping persistente
3. Utilizzare il nuovo `response_id` nelle iterazioni successive

```python
# Prima (BUG):
resp_map[thread_id] = str(resp.id)
_save_responses_map(resp_map)
# prev_id rimaneva invariato nelle iterazioni successive

# Dopo (FIX):
prev_id = str(resp.id)  # ✅ Aggiorna per prossima iterazione
resp_map[thread_id] = prev_id
_save_responses_map(resp_map)
```

---

## 📊 Monitoraggio delle Conversazioni

### 🖥️ Come Vedere i Log

#### **Frappe Cloud (Produzione)**

1. **Via Dashboard Web:**
   - Accedi al tuo sito su [https://frappecloud.com](https://frappecloud.com)
   - Vai su **Overview** → **Logs**
   - Seleziona **App Logs** o **Web Logs**
   - Cerca `ai_module` nella search bar

2. **Via Bench Console (SSH):**
   ```bash
   # Se hai accesso SSH al server
   ssh your-server
   cd /home/frappe/frappe-bench
   
   # Log in tempo reale
   tail -f sites/<site-name>/logs/bench.log | grep ai_module
   
   # Ultimi 100 log
   tail -100 sites/<site-name>/logs/bench.log | grep ai_module
   
   # Log specifici di WhatsApp
   tail -f sites/<site-name>/logs/bench.log | grep -E "ai_module|whatsapp"
   ```

3. **Via Error Log nel Browser:**
   - Nel tuo sito Frappe, vai su: **Home** → **Error Log**
   - Filtra per `ai_module` o cerca l'orario del problema
   - Questo mostra solo gli errori, non i log INFO

#### **Frappe Manager (Locale con WSL/Ubuntu)**

1. **Aprire WSL:**
   ```bash
   # Da Windows Terminal o PowerShell
   wsl
   ```

2. **Navigare al Bench:**
   ```bash
   # Trova il tuo bench (solitamente in /home o /workspaces)
   cd ~/frappe-bench
   # oppure
   cd /workspaces/frappe-bench
   
   # Verifica che sei nella directory corretta
   ls -la sites/
   ```

3. **Log in Tempo Reale (CONSIGLIATO):**
   ```bash
   # Log completo in tempo reale
   fm logs
   
   # O direttamente con tail
   tail -f sites/<site-name>/logs/bench.log
   
   # Filtra solo AI module
   tail -f sites/<site-name>/logs/bench.log | grep ai_module
   
   # Filtra AI + WhatsApp
   tail -f sites/<site-name>/logs/bench.log | grep -E "ai_module|whatsapp"
   ```

4. **Visualizzare Log Precedenti:**
   ```bash
   # Ultimi 200 log
   tail -200 sites/<site-name>/logs/bench.log
   
   # Ultimi 200 log filtrati per ai_module
   tail -200 sites/<site-name>/logs/bench.log | grep ai_module
   
   # Cerca log di oggi con orario
   grep "$(date +%Y-%m-%d)" sites/<site-name>/logs/bench.log | grep ai_module
   ```

5. **Log con Frappe Manager:**
   ```bash
   # Vedi tutti i log del bench
   fm logs
   
   # Vedi log di un sito specifico
   fm logs --site <site-name>
   
   # Segui log in tempo reale
   fm logs --follow
   ```

6. **Aprire Due Terminali WSL (TECNICA UTILE):**
   
   **Terminale 1 - Log Watcher:**
   ```bash
   cd ~/frappe-bench
   tail -f sites/<site-name>/logs/bench.log | grep ai_module
   ```
   
   **Terminale 2 - Interazione:**
   ```bash
   # Qui puoi inviare messaggi WhatsApp e vedere immediatamente i log nel Terminale 1
   # Oppure eseguire comandi bench
   cd ~/frappe-bench
   bench --site <site-name> console
   ```

#### **Come Trovare il Nome del Tuo Sito**

```bash
# Lista tutti i siti nel bench
ls sites/

# O con Frappe Manager
fm list

# Output esempio:
# sites/
# ├── assets/
# ├── common_site_config.json
# ├── your-site.local/
# └── another-site.com/
```

Il nome del sito è la cartella (es: `your-site.local`).

#### **Comandi Utili per Debugging**

```bash
# Log con timestamp e colori (richiede ccze)
tail -f sites/<site-name>/logs/bench.log | grep ai_module | ccze -A

# Log solo errori
tail -f sites/<site-name>/logs/bench.log | grep -E "ERROR|CRITICAL"

# Log di una sessione specifica (sostituisci con il numero reale)
tail -f sites/<site-name>/logs/bench.log | grep "session=whatsapp_393331234567"

# Log con context (3 righe prima e dopo ogni match)
tail -100 sites/<site-name>/logs/bench.log | grep -B 3 -A 3 "ai_module"

# Conta quanti messaggi AI sono stati elaborati oggi
grep "$(date +%Y-%m-%d)" sites/<site-name>/logs/bench.log | grep "AI request" | wc -l

# Vedi tutte le conversazioni attive (session IDs)
tail -200 sites/<site-name>/logs/bench.log | grep "session=" | grep -oP "session=\S+" | sort -u

# Traccia una conversazione specifica dall'inizio
grep "session=whatsapp_393331234567" sites/<site-name>/logs/bench.log | tail -20
```

---

### 🚀 Quick Start - Test Immediato

#### **Scenario 1: Voglio vedere i log ADESSO (Locale WSL)**

```bash
# 1. Apri WSL
wsl

# 2. Vai al bench
cd ~/frappe-bench

# 3. Trova il nome del sito
ls sites/
# Prendi nota del nome (es: techloop.local)

# 4. Avvia log watcher
tail -f sites/techloop.local/logs/bench.log | grep ai_module

# 5. Ora invia un messaggio WhatsApp al tuo sistema
#    Vedrai apparire i log in tempo reale! 🎉
```

#### **Scenario 2: Qualcosa non funziona, voglio vedere cosa c'è stato**

```bash
cd ~/frappe-bench

# Vedi gli ultimi 100 log di ai_module
tail -100 sites/techloop.local/logs/bench.log | grep ai_module

# Vedi anche errori
tail -200 sites/techloop.local/logs/bench.log | grep -E "ai_module|ERROR"
```

#### **Scenario 3: Frappe Cloud - Controllo via Browser**

1. Vai su https://frappecloud.com
2. Seleziona il tuo sito
3. Click su **"Logs"** nel menu laterale
4. Seleziona **"App Logs"**
5. Nella search bar scrivi: `ai_module`
6. Imposta il range temporale (es: Last 1 hour)
7. Refresh per vedere nuovi log

#### **Scenario 4: Due Terminali per Debug Interattivo (WSL)**

**Terminale 1:**
```bash
wsl
cd ~/frappe-bench
tail -f sites/techloop.local/logs/bench.log | grep -E "ai_module|whatsapp"
```

**Terminale 2:**
```bash
wsl
cd ~/frappe-bench

# Test manuale
bench --site techloop.local console

>>> from ai_module.agents.threads import run_with_responses_api
>>> result = run_with_responses_api("Ciao, mi chiamo Mario", "test_session_123")
>>> print(result)
```

Vedrai i log apparire in tempo reale nel Terminale 1! 🔥

---

### 📖 Cheat Sheet Frappe Manager

```bash
# Lista siti
fm list

# Log in tempo reale
fm logs --follow

# Log di un sito specifico
fm logs --site techloop.local --follow

# Info sul bench
fm info

# Console interattiva
fm shell --site techloop.local

# Restart servizi
fm restart

# Status servizi
fm status
```

### 📖 Cheat Sheet Bench Classico

```bash
# Log file
tail -f sites/<site>/logs/bench.log

# Console Python
bench --site <site> console

# Restart
bench restart

# Migrate
bench --site <site> migrate

# Rebuild
bench build

# Supervisor status (se usi supervisor)
supervisorctl status all
```

---

### Log Disponibili nel Terminale Bench

Quando l'AI elabora un messaggio, vedrai log come questi:

```bash
# Nuova conversazione
[ai_module.threads] INFO: Starting new conversation: session=whatsapp_393331234567

# Continuazione conversazione
[ai_module.threads] INFO: Continuing conversation: session=whatsapp_393331234567 prev_response=resp_abc123def456...

# Salvataggio response_id
[ai_module.threads] DEBUG: Saved response_id for session whatsapp_393331234567: resp_xyz789...

# Esecuzione tools
[ai_module.threads] INFO: Executing tools: update_contact_from_thread

# Risposta finale
[ai_module.threads] INFO: AI response: text_len=142 session=whatsapp_393331234567
```

### File di Persistenza

Il sistema mantiene questi file JSON in `sites/<site>/private/files/`:

1. **`ai_whatsapp_threads.json`**
   - Mapping: `phone_number` → `session_id`
   - Es: `"+393331234567": "whatsapp_393331234567"`

2. **`ai_response_map.json`** ⭐ NUOVO
   - Mapping: `session_id` → `response_id`
   - Es: `"whatsapp_393331234567": "resp_abc123def456789"`
   - Questo mantiene la continuità della conversazione

3. **`ai_language_map.json`**
   - Mapping: `phone_number` → `detected_language`
   - Es: `"+393331234567": "it"`

4. **`ai_human_activity.json`**
   - Mapping: `phone_number` → `last_activity_timestamp`
   - Per il cooldown delle risposte automatiche

---

## 🔍 Come Verificare che Funzioni

### Test 1: Invia Due Messaggi Consecutivi

```
Messaggio 1: "Ciao, mi chiamo Mario"
Messaggio 2: "Come mi chiamo?"
```

**Risultato Atteso:**
- Prima risposta: "Ciao Mario! Come posso aiutarti?"
- Seconda risposta: "Ti chiami Mario" (dimostra che ricorda)

### Test 2: Controlla i Log

Osserva il terminale bench dopo ogni messaggio:

```bash
# Primo messaggio
[ai_module.threads] INFO: Starting new conversation: session=whatsapp_393331234567
[ai_module.threads] DEBUG: Saved response_id for session whatsapp_393331234567: resp_abc123...
[ai_module.threads] INFO: AI response: text_len=142 session=whatsapp_393331234567

# Secondo messaggio (deve dire "Continuing")
[ai_module.threads] INFO: Continuing conversation: session=whatsapp_393331234567 prev_response=resp_abc123...
[ai_module.threads] DEBUG: Saved response_id for session whatsapp_393331234567: resp_def456...
[ai_module.threads] INFO: AI response: text_len=89 session=whatsapp_393331234567
```

### Test 3: Verifica i File JSON

```bash
# Connettiti al container o server
bench --site <site_name> console

# In Python console:
import json
from frappe.utils import get_site_path

# Verifica response mapping
with open(get_site_path("private", "files", "ai_response_map.json")) as f:
    print(json.dumps(json.load(f), indent=2))
```

**Output Atteso:**
```json
{
  "whatsapp_393331234567": "resp_xyz789abc123def456..."
}
```

---

## ⚠️ Problemi Comuni

### 1. AI Non Risponde Affatto

**Sintomi:** Nessun messaggio inviato dopo che l'utente scrive.

**Cause Possibili:**
- `AI_AUTOREPLY=false` in env
- Cooldown umano attivo (hai scritto un messaggio manuale di recente)
- Errore nella API key di OpenAI

**Check:**
```bash
# Verifica env
bench --site <site_name> console
> from ai_module.agents.config import get_environment
> env = get_environment()
> print(env.get("AI_AUTOREPLY"))  # Deve essere "true"
> print(bool(env.get("OPENAI_API_KEY")))  # Deve essere True
```

### 2. AI Risponde Ma Perde Contesto

**Sintomi:** Ogni risposta sembra una nuova conversazione.

**Causa:** Il mapping `response_id` non viene salvato correttamente.

**Check:**
```bash
# Verifica che il file esista e si aggiorni
ls -la sites/<site>/private/files/ai_response_map.json

# Osserva il file dopo ogni messaggio
watch -n 1 "cat sites/<site>/private/files/ai_response_map.json | jq"
```

**Fix:**
- Verifica permessi del file (deve essere writable da frappe user)
- Controlla log per errori I/O
- Prova a resettare la persistenza: vedi sezione sotto

### 3. Errore "BadRequestError"

**Sintomi:** Crash con `BadRequestError` nei log.

**Causa:** Parametri non validi inviati alla Responses API.

**Check nei log:**
```
[ai_module.threads] ERROR: AI API bad request: ...
```

**Possibili Cause:**
- `previous_response_id` non valido (es: response cancellato da OpenAI)
- Formato `input` non corretto
- Tool schema malformato

**Fix:**
```bash
# Reset della persistenza
bench --site <site_name> console
> from ai_module.api import ai_reset_persistence
> ai_reset_persistence(clear_threads=True)
```

---

## 🔄 Reset della Persistenza

Se le conversazioni sono "corrotte", puoi resettare tutto:

### Via API (consigliato):

```bash
bench --site <site_name> console

from ai_module.api import ai_reset_persistence
result = ai_reset_persistence(clear_threads=True)
print(result)
```

**Output:**
```python
{
  'success': True,
  'deleted': {
    'thread_map': True,
    'response_map': True,
    'language_map': True,
    'human_activity_map': True
  }
}
```

### Via File System (se API non funziona):

```bash
cd sites/<site_name>/private/files/
rm -f ai_whatsapp_threads.json
rm -f ai_response_map.json
rm -f ai_language_map.json
rm -f ai_human_activity.json

# Restart bench
bench restart
```

---

## 📝 Note sulla Responses API vs Threads API

### Cosa È Cambiato

**Prima (Threads API - DEPRECATO):**
- Ogni conversazione era un "Thread" persistente su OpenAI
- Potevi vedere i thread nel dashboard OpenAI
- Usavamo `assistant_id` e `thread_id`

**Ora (Responses API - MODERNO):**
- Ogni messaggio crea una nuova "Response" su OpenAI
- Le response sono collegate tramite `previous_response_id`
- Non ci sono thread persistenti nel dashboard OpenAI
- Il contesto è mantenuto localmente + previous_response_id

### Perché Non Vedi Più i Thread su OpenAI

Questo è **NORMALE** con la Responses API. Le conversazioni esistono solo come catena di response collegate, non come oggetti thread persistenti nel dashboard.

**Il contesto è mantenuto tramite:**
1. `previous_response_id` passato a ogni nuova response
2. Mapping locale in `ai_response_map.json`

---

## 🆘 Supporto

Se il problema persiste:

1. **Raccogli i log:**
   ```bash
   tail -f sites/<site_name>/logs/bench.log | grep ai_module
   ```

2. **Verifica i file JSON:**
   ```bash
   cat sites/<site_name>/private/files/ai_response_map.json
   ```

3. **Testa con conversazione semplice:**
   - Messaggio 1: "Ciao"
   - Messaggio 2: "Cosa ho detto prima?"
   - Se risponde correttamente, il sistema funziona ✅

4. **Controlla la documentazione:**
   - `README.md` - Architettura generale
   - `AI_WHATSAPP_REPLY_MODES.md` - Dettagli WhatsApp integration
   - `MIGRATION.md` - Guida migrazione da Threads API

---

## ✅ Checklist Verifica Rapida

- [ ] Log mostrano "Continuing conversation" per messaggi successivi
- [ ] File `ai_response_map.json` esiste e si aggiorna
- [ ] AI ricorda informazioni dai messaggi precedenti
- [ ] Tool vengono eseguiti correttamente quando necessario
- [ ] Nessun errore "BadRequestError" nei log
- [ ] `OPENAI_API_KEY` configurata correttamente
- [ ] `AI_AUTOREPLY=true` (se vuoi risposte automatiche)

---

**Ultima modifica:** 2025-01-16  
**Versione:** 1.0 (Post-migrazione Responses API)

