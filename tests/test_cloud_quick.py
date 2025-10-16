"""
AI Module - Quick Cloud Diagnostic

Test rapido per diagnosticare problemi su Frappe Cloud.
Esegui questo PRIMA di tutto quando l'AI non risponde.

COME USARE:
    bench console
    >>> exec(open('apps/ai_module/tests/test_cloud_quick.py').read())
"""
import frappe
import json
import os

print("\n" + "🔍 "* 25)
print("QUICK CLOUD DIAGNOSTIC - AI MODULE")
print("🔍 " * 25)

# ============================================================
# TEST 1: Codice Deployato?
# ============================================================
print("\n" + "="*70)
print("TEST 1: CODICE AGGIORNATO DEPLOYATO?")
print("="*70)

try:
    from ai_module.agents import threads
    import inspect
    
    source = inspect.getsource(threads.run_with_responses_api)
    
    # Cerca keywords del fix
    keywords = [
        ("tool_results as user message", "Tool results as user messages" in source or "role: \"user\"" in source),
        ("function_call type", "FUNCTION_CALL" in source or "function_call" in source),
        ("iteration check", "iteration == 1" in source)
    ]
    
    all_present = True
    for desc, present in keywords:
        status = "✅" if present else "❌"
        print(f"{status} {desc}: {'presente' if present else 'MANCANTE'}")
        if not present:
            all_present = False
    
    if all_present:
        print("\n✅ CODICE AGGIORNATO PRESENTE")
    else:
        print("\n❌ CODICE VECCHIO! Devi fare:")
        print("   1. git push origin develop")
        print("   2. Deploy da Frappe Cloud dashboard")
        print("   3. Aspetta completamento deploy")
        print("   4. Riprova questo test")
        print("\n⚠️  STOP QUI - Fix il deploy prima di continuare!")
        exit()
        
except Exception as e:
    print(f"❌ ERRORE: {e}")
    exit()

# ============================================================
# TEST 2: API Key Configurata?
# ============================================================
print("\n" + "="*70)
print("TEST 2: OPENAI API KEY")
print("="*70)

try:
    from ai_module.agents.config import apply_environment, get_environment
    
    apply_environment()
    env = get_environment()
    api_key = env.get("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ API KEY NON CONFIGURATA!")
        print("\n🔧 SOLUZIONE:")
        print("   1. Vai in AI Assistant Settings")
        print("   2. Abilita 'Use Settings Override'")
        print("   3. Inserisci OpenAI API Key nel campo 'openai_api_key_value'")
        print("   4. Salva")
        print("\n⚠️  STOP QUI - Configura API key prima di continuare!")
        exit()
    
    print(f"✅ API Key presente: {api_key[:15]}...{api_key[-4:]}")
    
except Exception as e:
    print(f"❌ ERRORE: {e}")
    exit()

# ============================================================
# TEST 3: AI Assistant Settings
# ============================================================
print("\n" + "="*70)
print("TEST 3: CONFIGURAZIONE AI")
print("="*70)

try:
    settings = frappe.get_single("AI Assistant Settings")
    
    issues = []
    
    print(f"Use Settings Override: {bool(settings.use_settings_override)}")
    print(f"WhatsApp AutoReply: {bool(settings.wa_enable_autoreply)}")
    print(f"WhatsApp Inline: {bool(settings.wa_force_inline)}")
    
    if not settings.wa_enable_autoreply:
        issues.append("AutoReply disabilitato")
    
    if issues:
        print(f"\n⚠️  PROBLEMI TROVATI:")
        for issue in issues:
            print(f"   - {issue}")
        print("\n🔧 SOLUZIONE:")
        print("   1. Vai in AI Assistant Settings")
        print("   2. Abilita 'wa_enable_autoreply'")
        print("   3. Salva")
    else:
        print("\n✅ Configurazione OK")
    
except Exception as e:
    print(f"❌ ERRORE: {e}")

# ============================================================
# TEST 4: File Sessioni Esistono?
# ============================================================
print("\n" + "="*70)
print("TEST 4: FILE SESSIONI")
print("="*70)

try:
    site_path = frappe.utils.get_site_path()
    files_dir = os.path.join(site_path, "private", "files")
    
    print(f"Path: {files_dir}")
    
    if not os.path.exists(files_dir):
        print(f"❌ Directory private/files non esiste!")
    else:
        print(f"✅ Directory esiste")
        
        # Verifica file
        response_file = os.path.join(files_dir, "ai_whatsapp_responses.json")
        if os.path.exists(response_file):
            with open(response_file, "r") as f:
                content = f.read().strip()
            if content:
                data = json.loads(content)
                print(f"✅ ai_whatsapp_responses.json: {len(data)} sessioni")
            else:
                print(f"✅ ai_whatsapp_responses.json: vuoto (normale per primo avvio)")
        else:
            print(f"⚠️  ai_whatsapp_responses.json non esiste (sarà creato al primo messaggio)")
    
except Exception as e:
    print(f"❌ ERRORE: {e}")

# ============================================================
# TEST 5: Test Connessione OpenAI
# ============================================================
print("\n" + "="*70)
print("TEST 5: TEST CONNESSIONE OPENAI")
print("="*70)

try:
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key)
    
    print("Tentativo chiamata API...")
    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[{"role": "user", "content": [{"type": "input_text", "text": "test"}]}]
    )
    
    print(f"✅ CONNESSIONE OK!")
    print(f"   Response ID: {resp.id[:30]}...")
    
except Exception as e:
    print(f"❌ CONNESSIONE FALLITA: {e}")
    print("\n🔧 POSSIBILI CAUSE:")
    print("   - API key invalida")
    print("   - Firewall blocca connessioni")
    print("   - Problema rete Frappe Cloud")
    exit()

# ============================================================
# TEST 6: Ultimi Messaggi WhatsApp
# ============================================================
print("\n" + "="*70)
print("TEST 6: MESSAGGI WHATSAPP RECENTI (ultime 24h)")
print("="*70)

try:
    yesterday = frappe.utils.add_to_date(frappe.utils.now(), days=-1)
    
    messages = frappe.get_all(
        "WhatsApp Message",
        filters={"creation": [">", yesterday]},
        fields=["name", "type", "message", "creation"],
        order_by="creation desc",
        limit=10
    )
    
    if not messages:
        print("⚠️  Nessun messaggio nelle ultime 24h")
        print("   → Invia un messaggio WhatsApp di test!")
    else:
        incoming = [m for m in messages if m.type == "Incoming"]
        outgoing = [m for m in messages if m.type == "Outgoing"]
        
        print(f"Totale: {len(messages)} messaggi")
        print(f"  📨 Incoming: {len(incoming)}")
        print(f"  📤 Outgoing: {len(outgoing)}")
        
        if incoming and not outgoing:
            print("\n⚠️  PROBLEMA: Messaggi ricevuti ma NESSUNA risposta inviata!")
            print("   → L'AI non sta processando i messaggi")
        
        print("\nUltimi 5:")
        for msg in messages[:5]:
            icon = "📨" if msg.type == "Incoming" else "📤"
            print(f"  {icon} {msg.creation}: {msg.message[:50]}...")
    
except Exception as e:
    print(f"❌ ERRORE: {e}")

# ============================================================
# TEST 7: Ultimi Errori
# ============================================================
print("\n" + "="*70)
print("TEST 7: ERRORI RECENTI AI MODULE")
print("="*70)

try:
    errors = frappe.get_all(
        "Error Log",
        filters={
            "method": ["like", "%ai_module%"],
            "creation": [">", frappe.utils.add_to_date(frappe.utils.now(), hours=-2)]
        },
        fields=["name", "method", "creation"],
        order_by="creation desc",
        limit=3
    )
    
    if not errors:
        print("✅ Nessun errore AI Module nelle ultime 2 ore")
    else:
        print(f"⚠️  {len(errors)} errori trovati:")
        
        for err_info in errors:
            err = frappe.get_doc("Error Log", err_info.name)
            print(f"\n{err.creation} - {err.method}")
            
            # Mostra ultima riga con errore
            lines = err.error.split('\n')
            for line in lines[-5:]:
                if 'Error' in line:
                    print(f"   → {line.strip()[:100]}")
                    break
    
except Exception as e:
    print(f"⚠️  Errore nel recupero errori: {e}")

# ============================================================
# TEST 8: Hook Registrato?
# ============================================================
print("\n" + "="*70)
print("TEST 8: HOOK WHATSAPP REGISTRATO")
print("="*70)

try:
    hooks = frappe.get_hooks("doc_events") or {}
    whatsapp_hooks = hooks.get("WhatsApp Message", {})
    after_insert = whatsapp_hooks.get("after_insert", [])
    
    ai_hook = [h for h in after_insert if "ai_module" in str(h)]
    
    if ai_hook:
        print(f"✅ Hook registrato: {ai_hook}")
    else:
        print(f"❌ HOOK NON REGISTRATO!")
        print(f"   Hooks trovati: {after_insert}")
        print("\n🔧 SOLUZIONE:")
        print("   1. Verifica hooks.py")
        print("   2. bench restart")
    
except Exception as e:
    print(f"⚠️  {e}")

# ============================================================
# RIEPILOGO
# ============================================================
print("\n" + "="*70)
print("📊 RIEPILOGO")
print("="*70)

print("\n🎯 PROSSIMI PASSI:")
print("\n1. Se vedi ❌ sopra, risolvi quei problemi PRIMA")
print("\n2. Se tutto ✅, invia un messaggio WhatsApp di test:")
print("   → 'Ciao!'")
print("\n3. Aspetta 5-10 secondi")
print("\n4. Se NON ricevi risposta, esegui di nuovo questo test")
print("   e controlla la sezione ERRORI RECENTI")
print("\n5. Se ricevi risposta, prova un messaggio con tool:")
print("   → 'Aggiungimi: Test User, test@test.com, Test Corp'")

print("\n" + "="*70)
print("Fine diagnostica")
print("="*70)

