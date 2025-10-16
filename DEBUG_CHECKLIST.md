# Debug Checklist - Log Vuoti AI Module

## 🔍 Passo 1: Verifica Configurazione Base

### A. Controlla che l'app sia installata

```bash
# In WSL
cd ~/frappe-bench

# Lista app installate
bench --site NOME_SITO list-apps

# Deve mostrare:
# frappe
# crm
# ai_module  ✅ <- Questo deve esserci
```

### B. Verifica Environment Variables

```bash
bench --site NOME_SITO console
```

```python
# In console Python
from ai_module.agents.config import get_environment

env = get_environment()

# Verifica API key
print("API Key presente:", bool(env.get("OPENAI_API_KEY")))
print("AutoReply attivo:", env.get("AI_AUTOREPLY"))
print("Model:", env.get("AI_ASSISTANT_MODEL"))

# Se API Key è False, QUESTO È IL PROBLEMA!
```

**Risultato atteso:**
```python
API Key presente: True  ✅
AutoReply attivo: true  ✅
Model: gpt-4o-mini
```

---

## 🔍 Passo 2: Verifica Hook WhatsApp

### A. Controlla che l'hook sia registrato

```bash
bench --site NOME_SITO console
```

```python
# Verifica hook
import frappe

hooks = frappe.get_hooks("doc_events")
whatsapp_hooks = hooks.get("WhatsApp Message", {})

print("Hook after_insert:", whatsapp_hooks.get("after_insert"))

# Deve mostrare:
# ['ai_module.integrations.whatsapp.on_whatsapp_after_insert']
```

### B. Verifica che il DocType WhatsApp Message esista

```python
# In console
print(frappe.db.exists("DocType", "WhatsApp Message"))
# Deve essere: True
```

---

## 🔍 Passo 3: Test Manuale WhatsApp Message

### Simula un messaggio in arrivo

```bash
bench --site NOME_SITO console
```

```python
# Crea un messaggio WhatsApp di test
msg = frappe.get_doc({
    "doctype": "WhatsApp Message",
    "type": "Incoming",
    "from": "+393331234567",
    "message": "Ciao, questo è un test",
    "message_type": "text"
})

# Inserisci (questo dovrebbe triggerare l'hook)
msg.insert()

print(f"Messaggio creato: {msg.name}")

# ORA controlla i log!
# Esci dalla console (Ctrl+D) e fai:
# tail -50 sites/NOME_SITO/logs/ai_module.whatsapp.log
```

**Se vedi log dopo questo, il problema è che non arrivano messaggi WhatsApp veri.**

---

## 🔍 Passo 4: Verifica Log Standard (bench.log)

I log potrebbero essere nel `bench.log` principale invece che nei file specifici.

```bash
# Cerca log ai_module
tail -100 sites/NOME_SITO/logs/bench.log | grep -i ai_module

# Cerca errori generali
tail -200 sites/NOME_SITO/logs/bench.log | grep -i error

# Cerca log whatsapp
tail -100 sites/NOME_SITO/logs/bench.log | grep -i whatsapp
```

---

## 🔍 Passo 5: Verifica Connessione WhatsApp

### Il CRM sta ricevendo messaggi WhatsApp?

```bash
bench --site NOME_SITO console
```

```python
# Cerca messaggi WhatsApp recenti
messages = frappe.get_all(
    "WhatsApp Message",
    filters={"type": "Incoming"},
    fields=["name", "from", "message", "creation"],
    order_by="creation desc",
    limit=10
)

for msg in messages:
    print(f"{msg.creation}: {msg.from} - {msg.message[:50]}")

# Se è vuoto, il problema è la connessione WhatsApp!
```

**Se non ci sono messaggi, il CRM non sta ricevendo messaggi WhatsApp.**

---

## 🔍 Passo 6: Test Diretto Funzione AI

### Testa direttamente la funzione AI (senza WhatsApp)

```bash
bench --site NOME_SITO console
```

```python
from ai_module.agents.threads import run_with_responses_api

# Test diretto
result = run_with_responses_api(
    message="Ciao, questo è un test",
    session_id="test_debug_123",
    timeout_s=120
)

print("Risultato:", result)

# Se questo funziona, l'AI è OK e il problema è l'integrazione WhatsApp
# Se dà errore, il problema è nella configurazione AI
```

**Errori possibili:**
- `AuthenticationError`: OPENAI_API_KEY mancante o sbagliata
- `BadRequestError`: Problema con parametri
- `Timeout`: OpenAI non risponde

---

## 🔧 Soluzioni Comuni

### Problema 1: API Key Mancante

```bash
# Aggiungi in site_config.json
bench --site NOME_SITO set-config OPENAI_API_KEY "sk-..."

# Oppure in common_site_config.json per tutti i siti
nano sites/common_site_config.json

# Aggiungi:
{
  "OPENAI_API_KEY": "sk-..."
}

# Restart
bench restart
```

### Problema 2: AutoReply Disabilitato

```bash
bench --site NOME_SITO set-config AI_AUTOREPLY "true"
bench restart
```

### Problema 3: Hook Non Registrato

```bash
# Re-installa l'app
bench --site NOME_SITO uninstall-app ai_module
bench --site NOME_SITO install-app ai_module
bench restart
```

### Problema 4: WhatsApp Non Configurato

Verifica nel CRM:
1. **WhatsApp Settings** → Connessione attiva
2. Webhook configurato correttamente
3. Test con invio messaggio dal CRM

---

## 📊 Interpretazione Risultati

### Scenario A: Test manuale funziona, messaggi veri no
→ **Problema:** Connessione WhatsApp o hook non triggerato  
→ **Soluzione:** Verifica WhatsApp Settings nel CRM

### Scenario B: API Key mancante
→ **Problema:** Configurazione  
→ **Soluzione:** Aggiungi OPENAI_API_KEY in site_config

### Scenario C: Test diretto AI fallisce
→ **Problema:** Configurazione OpenAI o network  
→ **Soluzione:** Verifica API key, connessione internet, firewall

### Scenario D: Tutto funziona in test, log ancora vuoti
→ **Problema:** Livello log troppo alto  
→ **Soluzione:** Non è un problema, i log vengono creati solo quando c'è attività

---

## 🚀 Quick Debug Script

Salva questo in un file `debug_ai.py`:

```python
#!/usr/bin/env python3
import frappe

def debug_ai_module():
    """Debug completo AI Module"""
    
    print("=== AI Module Debug ===\n")
    
    # 1. Environment
    from ai_module.agents.config import get_environment
    env = get_environment()
    print("✓ API Key:", "Presente" if env.get("OPENAI_API_KEY") else "❌ MANCANTE")
    print("✓ AutoReply:", env.get("AI_AUTOREPLY", "false"))
    print("✓ Model:", env.get("AI_ASSISTANT_MODEL", "default"))
    print()
    
    # 2. Hooks
    hooks = frappe.get_hooks("doc_events")
    wa_hooks = hooks.get("WhatsApp Message", {})
    print("✓ Hook WhatsApp:", "Registrato" if wa_hooks else "❌ MANCANTE")
    print()
    
    # 3. Messaggi recenti
    messages = frappe.get_all(
        "WhatsApp Message",
        filters={"type": "Incoming"},
        fields=["name", "creation"],
        order_by="creation desc",
        limit=5
    )
    print(f"✓ Messaggi WhatsApp recenti: {len(messages)}")
    for msg in messages:
        print(f"  - {msg.name} ({msg.creation})")
    print()
    
    # 4. Test AI
    print("🧪 Test AI...")
    try:
        from ai_module.agents.threads import run_with_responses_api
        result = run_with_responses_api("Test", "debug_session")
        print("✓ AI funziona! Risposta:", result.get("final_output", "")[:50])
    except Exception as e:
        print(f"❌ AI errore: {str(e)}")
    
    print("\n=== Fine Debug ===")

if __name__ == "__main__":
    frappe.init(site="NOME_SITO")  # Cambia con il tuo sito
    frappe.connect()
    debug_ai_module()
```

Esegui:
```bash
python debug_ai.py
```

---

## 📞 Prossimi Passi

Dopo aver eseguito questi check, dimmi:
1. Cosa mostra `get_environment()` (API key presente?)
2. Ci sono messaggi WhatsApp nel database?
3. Il test diretto AI funziona?

Con queste info posso aiutarti a risolvere! 🚀

