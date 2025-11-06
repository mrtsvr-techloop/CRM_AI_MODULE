# Integrazione Status Change Notifications - AI Module

## Panoramica

Questo documento descrive l'integrazione tra CRM e AI Module per inviare notifiche WhatsApp automatiche quando lo stato di un Lead cambia. Il modulo AI riceve dati strutturati dal CRM e genera messaggi personalizzati tramite AI.

## Componenti AI Module

### File Implementato

**`apps/ai_module/ai_module/integrations/status_change.py`**

Funzioni principali:
- `process_status_change_notification()`: Entry point per processare notifiche
- `_build_status_change_prompt()`: Costruisce prompt strutturato per AI

## Flusso di Integrazione

```
CRM Module
    ↓ (chiama)
process_status_change_notification(payload)
    ↓
Verifica moduli WhatsApp disponibili
    ↓
Ottiene/crea sessione telefono
    ↓
Costruisce prompt strutturato
    ↓
Chiama run_agent()
    ↓
Genera messaggio personalizzato
    ↓
Invia tramite _send_autoreply()
```

## Payload Ricevuto

Il modulo AI riceve un payload con questa struttura:

```python
{
    "phone": "+393331234567",
    "context": {
        "lead_id": "CRM-LEAD-2025-00001",
        "order_number": "CRM-LEAD-2025-00001",
        "old_status": "Nuovo",
        "new_status": "Attesa Pagamento",
        "customer_name": "Mario Rossi",
        "has_order_details": True,
        "order_summary": {
            "products": [...],
            "subtotal": 20.00,
            "net_total": 20.00,
            "currency": "EUR"
        },
        "payment_info": {
            "text": "...",  # Da Brand Settings
            "source": "settings"  # o "default"
        }
    },
    "lead_name": "CRM-LEAD-2025-00001",
    "reference_doctype": "CRM Lead",
    "reference_name": "CRM-LEAD-2025-00001"
}
```

## Gestione Informazioni Pagamento

### Due Modalità

1. **Da Brand Settings** (`source: "settings"`)
   - Legge testo libero da `FCRM Settings.payment_info_text`
   - L'AI interpreta e formatta automaticamente
   - Più flessibile per il cliente

2. **Default** (`source: "default"`)
   - Usa struttura dati predefinita
   - Fallback se Brand Settings non configurato
   - Include IBAN, PayPal, istruzioni strutturate

### Prompt per "Attesa Pagamento"

Quando `has_order_details` è `True` e `new_status` è "Attesa Pagamento", il prompt include:

1. Riepilogo ordine completo:
   - Lista prodotti con quantità e prezzi
   - Totale ordine

2. Informazioni pagamento:
   - Se `source == "settings"`: usa testo così com'è
   - Se `source == "default"`: formatta struttura dati

3. Istruzioni chiare per il pagamento

## Gestione Errori

### Controlli Implementati

1. **Verifica Moduli WhatsApp**
   - Controlla che `whatsapp` integration sia disponibile
   - Se non disponibile: logga errore e ritorna

2. **Verifica Numero Telefono**
   - Normalizza formato numero
   - Se mancante: logga warning e ritorna

3. **Gestione Eccezioni**
   - Tutte le eccezioni sono loggate con `frappe.log_error()`
   - Traceback completo incluso
   - Non blocca il sistema se fallisce

### Logging

Tutti gli eventi sono loggati:
- Inizio processamento notifica
- Sessione creata/trovata
- Risultato AI
- Invio messaggio riuscito/fallito
- Errori di importazione

## Dipendenze

### Moduli Richiesti

1. **WhatsApp Integration** (`ai_module.integrations.whatsapp`)
   - `_get_or_create_thread_for_phone()`
   - `_send_autoreply()`
   - `get_environment()`
   - `apply_environment()`

2. **AI Agents** (`ai_module.agents.runner`)
   - `run_agent()`

3. **Logger Utils** (`ai_module.agents.logger_utils`)
   - `get_resilient_logger()`

### Verifica Disponibilità

Il codice verifica sempre che i moduli siano disponibili prima di usarli:

```python
try:
    from .whatsapp import (
        _get_or_create_thread_for_phone,
        _send_autoreply,
    )
except ImportError as import_error:
    frappe.log_error(...)
    return
```

## Prompt Strutturato

Il sistema costruisce prompt dettagliati che guidano l'AI nella generazione del messaggio.

### Esempio Prompt per "Attesa Pagamento"

```
Sei un assistente AI per un'azienda che gestisce ordini.
Il cliente Mario Rossi ha un ordine con numero CRM-LEAD-2025-00001.
Lo stato dell'ordine è cambiato da 'Nuovo' a 'Attesa Pagamento'.

IMPORTANTE: Lo stato è 'Attesa Pagamento'. Devi includere:

1. Riepilogo completo dell'ordine:
- Prodotto 1: 2 x €10.00 = €20.00
Totale: €20.00

2. Informazioni per il pagamento:
[Testo da Brand Settings o struttura default]

3. Istruzioni chiare su come procedere con il pagamento.

Genera SOLO il messaggio WhatsApp, senza aggiungere spiegazioni o commenti.
```

## Note per Sistemi AI

Se stai leggendo questo documento come sistema AI:

1. **Entry Point**: `process_status_change_notification(payload)`
2. **Dependencies**: Richiede moduli WhatsApp e AI Agents
3. **Error Handling**: Tutte le eccezioni sono loggate, non soppresse
4. **Phone Normalization**: I numeri vengono normalizzati prima dell'uso
5. **Session Management**: Usa `_get_or_create_thread_for_phone()` per sessioni
6. **Message Sending**: Usa `_send_autoreply()` per inviare messaggi WhatsApp
7. **Prompt Building**: `_build_status_change_prompt()` costruisce prompt strutturati

## Troubleshooting

### Import Errors

Se ci sono errori di importazione:
1. Verifica che `ai_module.integrations.whatsapp` esista
2. Controlla che tutte le funzioni richieste siano disponibili
3. Verifica i log per dettagli specifici

### AI Non Genera Messaggio

1. Verifica che l'agente AI sia configurato correttamente
2. Controlla i log per vedere il prompt inviato
3. Verifica che il contesto sia completo

### Messaggio Non Inviato

1. Verifica che `_send_autoreply()` sia disponibile
2. Controlla che il numero telefono sia valido
3. Verifica i log WhatsApp per errori di invio

## Integrazione con CRM

Questo modulo è chiamato da:
- `crm.fcrm.doctype.crm_lead.status_change_notification._send_status_change_notification()`

Il CRM verifica sempre che `ai_module` sia installato prima di chiamare questa funzione.

## Sicurezza

- I numeri di telefono vengono normalizzati ma non modificati arbitrariamente
- Le sessioni sono gestite tramite mapping sicuro (phone → session_id)
- Tutti gli errori sono loggati per audit trail
- Le eccezioni non bloccano il sistema principale

