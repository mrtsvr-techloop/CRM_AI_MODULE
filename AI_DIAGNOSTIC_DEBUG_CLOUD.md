# 🔧 AI Diagnostic (Debug Cloud)

**Data**: 16/01/2025  
**Path**: `/ai-diagnostics`

Pagina web per diagnosticare problemi dell'AI Module su Frappe Cloud senza accesso alla console.

## 🔒 Avviso Sicurezza

**IMPORTANTE**: Questa pagina diagnostica contiene **informazioni sensibili del sistema** tra cui:
- Chiavi API (parzialmente mascherate)
- Configurazione sistema
- Log degli errori
- Dati delle sessioni
- Statistiche messaggi

**L'accesso è limitato solo agli utenti autenticati.** La pagina richiede credenziali di login e registra tutti i tentativi di accesso.

---

## 🚀 Avvio Rapido

### 1. Deploy su Frappe Cloud

```bash
git add -A
git commit -m "feat: add cloud diagnostics"
git push origin develop
```

Poi aggiorna l'app su Frappe Cloud Dashboard.

---

### 2. Apri Pagina Diagnostica

Naviga a:
```
https://TUO-SITO.frappe.cloud/ai-diagnostics
```

Sostituisci `TUO-SITO` con il nome effettivo del tuo sito Frappe Cloud.

**Ti verrà richiesto il login** con le credenziali Frappe prima di accedere alle diagnostiche.

### 3. Autenticazione

- **Se non loggato**: Verrai automaticamente rediretto alla pagina di login di Frappe
- **Se già loggato**: La pagina mostrerà il tuo username e eseguirà automaticamente le diagnostiche
- **Dopo il login**: Frappe ti riporterà alla pagina diagnostica

---

## 🔍 Cosa Controlla

### ✅ Codice Deployato
- Verifica se le ultime modifiche al codice sono deployate
- Controlla le firme delle funzioni critiche in `threads.py`
- **Stato**: `fail` significa che devi rifare il deploy (IGNORABILE)

### ✅ Chiave API
- Conferma che la chiave API OpenAI sia configurata
- Mostra i primi/ultimi caratteri per verifica
- **Stato**: `fail` significa che la chiave manca → controlla AI Assistant Settings

### ✅ Impostazioni
- Stato AutoReply (`wa_enable_autoreply`)
- Modalità inline (`wa_force_inline`)
- Timer cooldown umano
- **Stato**: `warning` se AutoReply è disabilitato

### ✅ File Sessioni
- Conta le sessioni AI attive
- Mostra lo stato di persistenza delle conversazioni
- **Stato**: `pass` sempre (informativo)

### ✅ Messaggi WhatsApp
- Conteggio messaggi in arrivo/in uscita (ultime 24h)
- Identifica problemi di comunicazione unidirezionale
- **Stato**: `fail` se vengono ricevuti messaggi ma nessuna risposta

### ✅ Errori Recenti
- Ultimi 3 errori dal modulo AI (finestra di 2h)
- Mostra tipo di errore e timestamp
- **Stato**: `fail` se esistono errori

---

## 🎯 Problemi Comuni e Soluzioni

### Problema: "Codice Deployato: FAIL"
**Soluzione**: Rifai il deploy dell'app su Frappe Cloud Dashboard

### Problema: "Chiave API: FAIL"
**Soluzione**: 
1. Vai su **AI Assistant Settings**
2. Abilita "Use Settings Override"
3. Inserisci la tua chiave API OpenAI
4. Salva

### Problema: "AutoReply: DISABILITATO"
**Soluzione**:
1. Vai su **AI Assistant Settings**
2. Abilita "WhatsApp AutoReply"
3. Salva

### Problema: "Messaggi ricevuti ma NESSUNA risposta"
**Soluzione**: Controlla la sezione **Errori Recenti** per l'errore specifico

---

## 🔄 Reset Sessioni

Se le conversazioni sono bloccate o corrotte:

1. Clicca il pulsante **"Reset Sessions"** nella pagina diagnostica
2. Conferma l'azione
3. Tutta la cronologia delle conversazioni AI verrà cancellata
4. Il prossimo messaggio inizierà una conversazione fresca

---

## 📡 Accesso API (Avanzato)

### Ottieni Diagnostiche (JSON)
```bash
curl https://TUO-SITO.frappe.cloud/api/method/ai_module.api.run_diagnostics \
  -H "Authorization: token API_KEY:API_SECRET"
```

### Reset Sessioni (JSON)
```bash
curl -X POST https://TUO-SITO.frappe.cloud/api/method/ai_module.api.reset_sessions \
  -H "Authorization: token API_KEY:API_SECRET"
```

**Nota**: L'accesso API richiede un token di autenticazione. Usa la funzione di generazione chiavi API di Frappe.

---

## 🔒 Funzionalità di Sicurezza

### Autenticazione Richiesta
- Tutti gli endpoint richiedono autenticazione Frappe valida
- Gli utenti Guest vengono automaticamente rediretti al login
- Usa la gestione sessioni integrata di Frappe

### Logging Accessi
- Tutti gli accessi diagnostici vengono registrati con utente e IP
- I reset delle sessioni vengono registrati come warning
- I log sono disponibili nel Log Errori di Frappe

### Restrizioni Ruoli Opzionali
Per limitare l'accesso solo ai System Manager, decommenta queste righe in `api.py`:
```python
# if not frappe.has_permission("System Manager"):
#     frappe.throw("System Manager role required", frappe.PermissionError)
```

---

## 🆘 Ancora Non Funziona?

1. **Controlla Log Frappe Cloud**:
   - Dashboard → Il Tuo Sito → Logs
   - Filtra per "ai_module"

2. **Verifica Integrazione WhatsApp**:
   - Controlla le impostazioni WhatsApp del CRM
   - Verifica le credenziali API Facebook

3. **Testa con Messaggio Semplice**:
   - Invia "ciao" al tuo numero WhatsApp
   - Controlla se viene generata una risposta

---

## 🔗 Documentazione Correlata

- [README Principale](README.md)
- [Migrazione Responses API](MIGRATION.md)
- [Guida Tool Calling](RESPONSES_API_TOOL_CALLING.md)
- [Guida Log Locali](LOG_GUIDE.md)

---

**Ultimo Aggiornamento**: 2025-01-16
