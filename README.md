# AI Module per Frappe

Modulo di integrazione AI per Frappe sviluppato da Techloop che permette di integrare modelli LLM (come OpenAI) nel tuo CRM, con supporto completo per WhatsApp e funzionalità avanzate di conversazione.

## Pregi del Sistema

### Integrazione Diretta Python
Il sistema non utilizza chiamate HTTP esterne tra componenti. Tutte le comunicazioni avvengono tramite codice Python nativo, garantendo:
- **Prestazioni elevate** - Nessun overhead di rete tra app
- **Affidabilità** - Nessun problema di timeout o connessione
- **Sicurezza** - Tutti i dati rimangono all'interno del server

### Architettura Moderna
Utilizza la moderna **OpenAI Responses API** invece della deprecata Assistants API, offrendo:
- **Configurazione flessibile** - Model, istruzioni e tools passati ad ogni chiamata
- **Nessun oggetto da gestire** - Non serve creare o aggiornare Assistant persistenti
- **Controllo totale** - Ogni chiamata può avere configurazioni diverse

### Sicurezza Avanzata
I numeri di telefono degli utenti **non vengono mai inviati a OpenAI**. Il sistema utilizza un mapping locale sicuro:
- Phone number → Session ID (mappato localmente)
- Solo il Session ID viene inviato a OpenAI
- I dati sensibili rimangono sempre sul server

### Funzionalità Complete
- **Continuità conversazionale** - Mantiene il contesto tra messaggi
- **Function calling** - L'AI può chiamare funzioni Python del CRM
- **Rilevamento lingua** - Rileva e memorizza automaticamente la lingua dell'utente
- **Creazione contatti automatica** - Crea nuovi contatti quando necessario
- **Human takeover** - Pausa automatica dell'AI quando un operatore interviene
- **Integrazione WhatsApp** - Auto-risposta completa ai messaggi WhatsApp

## Setup Veloce dal DocType

Il sistema può essere configurato completamente dall'interfaccia Frappe senza modificare file o variabili d'ambiente.

### Passo 1: Accedi alle Impostazioni
Vai su **AI Assistant Settings** nel menu di Frappe.

### Passo 2: Abilita la Configurazione dal DocType
Spunta la casella **"Use this DocType for configuration"**. Questo abilita tutti i campi di configurazione.

### Passo 3: Configura la Chiave API
Nel campo **"OpenAI API Key"**, inserisci la tua chiave API OpenAI. Il campo è criptato e sicuro.

### Passo 4: Configura il Modello
Nel campo **"Model"**, inserisci il modello da utilizzare (es. `gpt-4o-mini`, `gpt-4o`, ecc.).

### Passo 5: Personalizza le Istruzioni
Nel campo **"Instructions"**, inserisci il prompt di sistema per l'AI. Puoi usare il placeholder `{{Cliente}}` che verrà sostituito automaticamente con il nome del cliente configurato nel campo **"Nome Cliente"**.

### Passo 6: Configura WhatsApp (Opzionale)
Nella sezione **"WhatsApp Orchestration"**:
- **Enable auto-reply from AI**: Abilita le risposte automatiche (default: attivo)
- **Show reaction before AI processing**: Mostra reazione durante l'elaborazione (default: disattivo)
- **Human takeover cooldown**: Secondi di pausa dopo intervento umano (default: 0)

### Passo 7: Knowledge Base PDF (Opzionale)
Se vuoi che l'AI utilizzi un documento PDF come contesto:
- Abilita **"Enable PDF Knowledge Base"**
- Carica un PDF nella sezione **"Knowledge Base PDF"**
- Il sistema creerà automaticamente un Vector Store su OpenAI

### Passo 8: Salva
Clicca su **Salva**. Il sistema applicherà automaticamente tutte le configurazioni.

## AI Diagnostics

La pagina **ai-diagnostics** è uno strumento di diagnostica web che permette di verificare lo stato del sistema AI senza accesso alla console, particolarmente utile su Frappe Cloud.

### A Cosa Serve
Permette di diagnosticare problemi dell'AI Module quando non hai accesso diretto ai log o alla console del server. È ideale per:
- Verificare se il codice aggiornato è stato deployato correttamente
- Controllare se la chiave API è configurata
- Monitorare lo stato delle impostazioni (AutoReply, cooldown, ecc.)
- Analizzare le sessioni attive
- Visualizzare statistiche dei messaggi WhatsApp (ultime 24 ore)
- Identificare errori recenti del sistema

### Come Accedere
Naviga all'URL: `https://TUO-SITO.frappe.cloud/ai-diagnostics`

Sostituisci `TUO-SITO` con il nome del tuo sito Frappe Cloud. Se non sei autenticato, verrai reindirizzato al login.

### Cosa Controlla
La pagina esegue automaticamente diversi controlli:

**Codice Deployato**: Verifica se le ultime modifiche al codice sono state deployate correttamente.

**Chiave API**: Controlla se la chiave API OpenAI è configurata e valida, mostrando i primi e ultimi caratteri per verifica.

**Impostazioni**: Mostra lo stato di AutoReply, modalità inline e timer di cooldown.

**File Sessioni**: Conta le sessioni AI attive e mostra lo stato della persistenza delle conversazioni.

**Messaggi WhatsApp**: Mostra il conteggio dei messaggi in arrivo e in uscita delle ultime 24 ore, aiutando a identificare problemi di comunicazione unidirezionale.

**Errori Recenti**: Elenca gli ultimi errori del modulo AI (finestra di 2 ore) con tipo di errore e timestamp.

### Funzionalità Aggiuntive
La pagina include un pulsante **"Reset Sessions"** che permette di cancellare tutta la cronologia delle conversazioni AI se necessario. Utile quando le conversazioni sono bloccate o corrotte.

### Sicurezza
L'accesso alla pagina è limitato agli utenti autenticati. Tutti gli accessi vengono registrati con utente e indirizzo IP per tracciabilità.

## Funzionalità Avanzate

### Function Calling
L'AI può chiamare funzioni Python del CRM per eseguire azioni come:
- Cercare prodotti
- Creare ordini
- Aggiornare contatti
- Generare form di conferma ordine

I tool vengono caricati automaticamente dalla cartella `agents/tools/` e sono disponibili all'AI durante le conversazioni.

### Persistenza Conversazioni
Il sistema mantiene automaticamente il contesto delle conversazioni utilizzando:
- Mapping Phone → Session ID (file locale sicuro)
- Mapping Session → Response ID (per continuità OpenAI)
- Rilevamento e memorizzazione della lingua dell'utente

Tutti i file di persistenza sono privati e non accessibili dal web.

### Integrazione WhatsApp
Quando un messaggio WhatsApp viene ricevuto:
1. Il sistema crea automaticamente un record nel CRM
2. Mappa il numero di telefono a un Session ID sicuro
3. Invia il messaggio all'AI con il contesto della conversazione
4. Riceve la risposta e la invia automaticamente via WhatsApp
5. Salva il nuovo Response ID per la prossima conversazione

Tutto avviene in modo trasparente senza intervento manuale.

## Supporto e Documentazione

Per ulteriori informazioni e troubleshooting, consulta:
- **TROUBLESHOOTING.md** - Risoluzione problemi comuni
- **MIGRATION.md** - Guida migrazione da Assistants API
- **AI_WHATSAPP_REPLY_MODES.md** - Dettagli integrazione WhatsApp

## Licenza

Unlicense - Libero da usare, modificare e distribuire.
