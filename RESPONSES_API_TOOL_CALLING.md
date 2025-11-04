# OpenAI Responses API - Tool Calling Guide

## 🎯 Il Problema

La **OpenAI Responses API** ha limitazioni specifiche per il tool calling che non sono documentate chiaramente. Dopo numerosi test empirici, abbiamo scoperto il comportamento corretto.

---

## ❌ Cosa NON Funziona

### **Errore Comune: "No tool output found for function call XXX"**

Questo errore si verifica quando:

1. ✅ Prima chiamata con `previous_response_id` → AI chiama un tool
2. ❌ Salvi il `response_id` di questa risposta (che ha un tool_call in sospeso)
3. ❌ Nel messaggio successivo, usi questo `response_id` come `previous_response_id`
4. 💥 **Errore**: OpenAI si aspetta i tool results per quella chiamata precedente!

### **Problema con `role: "tool"`**

```python
# ❌ QUESTO NON FUNZIONA
input = [
    {"role": "tool", "content": [...], "tool_call_id": "xxx"}
]
# Errore: Invalid value: 'tool'. Supported values: 'assistant', 'system', 'user'
```

La Responses API **NON supporta `role: "tool"`**!

---

## ✅ La Soluzione Corretta

### **Regola 1: previous_response_id Solo per Continuità Conversazione**

```python
# ✅ CORRETTO
# Turno 1: Utente chiede info generali
resp1 = client.responses.create(
    input=[{"role": "user", "content": [{"type": "input_text", "text": "Ciao"}]}],
    previous_response_id=None
)
# Salvo: resp1.id

# Turno 2: Utente fa nuova domanda
resp2 = client.responses.create(
    input=[{"role": "user", "content": [{"type": "input_text", "text": "Come mi chiamo?"}]}],
    previous_response_id=resp1.id  # ← OK! Continuità tra turni utente
)
```

### **Regola 2: NON Usare previous_response_id nel Tool Calling Loop**

```python
# ❌ SBAGLIATO
# Iterazione 1: AI chiama tool
resp1 = client.responses.create(
    input=[{"role": "user", "content": [{"type": "input_text", "text": "Aggiorna contatto"}]}],
    previous_response_id=prev_conversation_id
)
# → function_call(update_contact)
# Salvo: resp1.id

# Iterazione 2: Fornisco tool result
resp2 = client.responses.create(
    input=[...tool results...],
    previous_response_id=resp1.id  # ❌ ERRORE! "No tool output found"
)
```

```python
# ✅ CORRETTO
# Iterazione 1: AI chiama tool
resp1 = client.responses.create(
    input=[{"role": "user", "content": [{"type": "input_text", "text": "Aggiorna contatto"}]}],
    previous_response_id=prev_conversation_id  # OK per continuità conversazione
)
# → function_call(update_contact)

# Eseguo tool → result = {"contact_id": "CONT-001"}

# Iterazione 2: Fornisco tool result
resp2 = client.responses.create(
    input=[
        {"role": "user", "content": [{"type": "input_text", "text": "Aggiorna contatto"}]},
        {"role": "user", "content": [{"type": "input_text", "text": f"Function update_contact returned: {result}"}]}
    ],
    previous_response_id=None  # ✅ NON uso resp1.id!
)
# → "Ho aggiornato il contatto CONT-001!"
```

### **Regola 3: Tool Results Come User Messages**

I tool results devono essere formattati come messaggi utente normali:

```python
# ✅ CORRETTO
tool_result = {"contact_id": "CONT-001", "success": True}
input = [
    {"role": "user", "content": [{"type": "input_text", "text": "Aggiorna contatto"}]},
    {"role": "user", "content": [{"type": "input_text", "text": f"Function update_contact returned: {json.dumps(tool_result)}"}]}
]
```

---

## 🔍 Dettagli Tecnici

### **Tipo di Output: `function_call`**

```python
resp = client.responses.create(...)
for item in resp.output:
    if item.type == "function_call":  # ← NON "tool_use"!
        call_id = item.call_id  # ← NON item.id!
        func_name = item.name
        func_args = item.arguments  # ← Stringa JSON, non dict!
```

### **Arguments è una Stringa JSON**

```python
# item.arguments è una stringa tipo: '{"city":"Roma"}'
args_dict = json.loads(item.arguments)
```

---

## 🎯 Pattern Completo

```python
from openai import OpenAI
import json

client = OpenAI(api_key="...")

# Step 1: Prima richiesta (con conversazione precedente)
resp1 = client.responses.create(
    model="gpt-4o-mini",
    input=[
        {"role": "user", "content": [{"type": "input_text", "text": "Crea lead per Mario Rossi"}]}
    ],
    tools=[...],
    previous_response_id=previous_conversation_response_id  # Continuità conversazione
)

# Step 2: Controlla se ci sono function calls
tool_calls = [item for item in resp1.output if item.type == "function_call"]

if tool_calls:
    # Step 3: Esegui tool
    for tool_call in tool_calls:
        func_name = tool_call.name
        func_args = json.loads(tool_call.arguments)
        
        # Esegui funzione
        result = execute_function(func_name, **func_args)
        
        # Step 4: Crea nuovo input con tool result
        # IMPORTANTE: NON usare previous_response_id di resp1!
        resp2 = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "user", "content": [{"type": "input_text", "text": "Crea lead per Mario Rossi"}]},
                {"role": "user", "content": [{"type": "input_text", "text": f"Function {func_name} returned: {json.dumps(result)}"}]}
            ],
            tools=[...],
            previous_response_id=None  # ← NON usare resp1.id!
        )
        
        # Step 5: Salva response_id finale per prossimo turno conversazione
        final_response_id = resp2.id
else:
    # Nessun tool call, salva response_id per prossimo turno
    final_response_id = resp1.id

# Salva per prossima conversazione utente
save_response_id(session_id, final_response_id)
```

---

## 📋 Checklist Implementazione

- [ ] Tool format corretto (name a livello root, non in function)
- [ ] Riconosci tipo `function_call` (non `tool_use`)
- [ ] Usa `call_id` (non `id`)
- [ ] Parsa `arguments` come JSON string
- [ ] Tool results come `role: "user"` messages
- [ ] `previous_response_id` solo per continuità tra turni utente
- [ ] NON usare `previous_response_id` nel tool calling loop
- [ ] Salva response_id FINALE (dopo tool execution)

---

## 🐛 Debugging

Se ottieni "No tool output found":
1. ✅ Stai usando `previous_response_id` nel tool calling loop → **Rimuovilo!**
2. ✅ Stai salvando response_id con tool_call in sospeso → **Salva solo l'ultimo!**

Se ottieni "Invalid value: 'tool'":
1. ✅ Stai usando `role: "tool"` → **Usa `role: "user"` invece!**

---

## 📚 Risorse

- Questo comportamento è stato scoperto tramite test empirici
- Non è documentato chiaramente nella documentazione ufficiale OpenAI
- La Responses API è relativamente nuova e può avere comportamenti non ovvi

---

**Ultimo aggiornamento**: 2025-10-16

