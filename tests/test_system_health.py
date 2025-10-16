"""
AI Module - System Health Check

Esegui questo script nella console Frappe per verificare lo stato del sistema.

COME USARE:
    bench console
    >>> exec(open('apps/ai_module/tests/test_system_health.py').read())
"""
import frappe
import json
import os
from datetime import datetime, timedelta

def print_section(title):
    print("\n" + "="*70)
    print(f"{title}")
    print("="*70)

def test_openai_connection():
    """Test 1: Connessione OpenAI"""
    print_section("TEST 1: CONNESSIONE OPENAI")
    
    try:
        from ai_module.agents.config import apply_environment, get_environment
        from openai import OpenAI
        
        apply_environment()
        env = get_environment()
        api_key = env.get("OPENAI_API_KEY")
        
        if not api_key:
            print("❌ OPENAI_API_KEY non configurato")
            return False
        
        print(f"✅ API Key presente: {api_key[:20]}...{api_key[-4:]}")
        
        # Test connessione
        client = OpenAI(api_key=api_key)
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=[{"role": "user", "content": [{"type": "input_text", "text": "test"}]}]
        )
        
        print(f"✅ Connessione OpenAI OK (response_id: {resp.id[:20]}...)")
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def test_ai_configuration():
    """Test 2: Configurazione AI Assistant"""
    print_section("TEST 2: CONFIGURAZIONE AI ASSISTANT")
    
    try:
        settings = frappe.get_single("AI Assistant Settings")
        
        print(f"Use Settings Override: {bool(settings.use_settings_override)}")
        print(f"Model: {settings.model or 'default (gpt-4o-mini)'}")
        print(f"Instructions: {len(settings.instructions or '')} caratteri")
        print(f"\nWhatsApp Settings:")
        print(f"  - AutoReply: {bool(settings.wa_enable_autoreply)}")
        print(f"  - Inline: {bool(settings.wa_force_inline)}")
        print(f"  - Cooldown: {settings.wa_human_cooldown_seconds}s")
        
        if settings.use_settings_override and not settings.instructions:
            print("⚠️  Override attivo ma instructions vuote")
        
        print("✅ Configurazione OK")
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def test_session_files():
    """Test 3: File Sessioni"""
    print_section("TEST 3: FILE SESSIONI WHATSAPP")
    
    site_path = frappe.utils.get_site_path()
    files_dir = os.path.join(site_path, "private", "files")
    
    files = [
        ("ai_whatsapp_responses.json", "Response IDs (continuità conversazione)"),
        ("ai_whatsapp_threads.json", "Phone -> Session mapping"),
        ("ai_whatsapp_lang.json", "Language preferences"),
        ("ai_whatsapp_handoffjson", "Human handoff status")
    ]
    
    all_ok = True
    
    for filename, description in files:
        filepath = os.path.join(files_dir, filename)
        
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    content = f.read().strip()
                
                if content:
                    data = json.loads(content)
                    print(f"✅ {filename}: {len(data)} entries - {description}")
                else:
                    print(f"⚠️  {filename}: VUOTO - {description}")
            except json.JSONDecodeError:
                print(f"❌ {filename}: CORROTTO - {description}")
                all_ok = False
        else:
            print(f"❌ {filename}: NON ESISTE - {description}")
            all_ok = False
    
    return all_ok

def test_recent_errors():
    """Test 4: Errori Recenti"""
    print_section("TEST 4: ERRORI RECENTI (ultime 24h)")
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    
    errors = frappe.get_all(
        "Error Log",
        filters={
            "method": ["like", "%ai_module%"],
            "creation": [">", yesterday]
        },
        fields=["name", "method", "creation"],
        order_by="creation desc",
        limit=5
    )
    
    if not errors:
        print("✅ Nessun errore nelle ultime 24h")
        return True
    
    print(f"⚠️  {len(errors)} errori trovati:")
    
    for err_info in errors:
        err = frappe.get_doc("Error Log", err_info.name)
        print(f"\n   {err.creation} - {err.method}")
        
        # Estrai tipo di errore
        error_lines = err.error.split('\n')
        for line in error_lines[-5:]:
            if 'Error' in line or 'error' in line:
                print(f"   → {line.strip()[:80]}")
                break
    
    return False

def test_whatsapp_messages():
    """Test 5: Messaggi WhatsApp Recenti"""
    print_section("TEST 5: MESSAGGI WHATSAPP (ultime 2 ore)")
    
    two_hours_ago = frappe.utils.add_to_date(frappe.utils.now(), hours=-2)
    
    messages = frappe.get_all(
        "WhatsApp Message",
        filters={"creation": [">", two_hours_ago]},
        fields=["name", "type", "message", "creation"],
        order_by="creation desc",
        limit=10
    )
    
    if not messages:
        print("⚠️  Nessun messaggio nelle ultime 2 ore")
        return True
    
    incoming = [m for m in messages if m.type == "Incoming"]
    outgoing = [m for m in messages if m.type == "Outgoing"]
    
    print(f"📊 Totale: {len(messages)} messaggi")
    print(f"   📨 Incoming: {len(incoming)}")
    print(f"   📤 Outgoing: {len(outgoing)}")
    
    if incoming and not outgoing:
        print("⚠️  Messaggi ricevuti ma nessuna risposta inviata!")
    
    print("\n   Ultimi 5 messaggi:")
    for msg in messages[:5]:
        icon = "📨" if msg.type == "Incoming" else "📤"
        print(f"   {icon} {msg.creation}: {msg.message[:50]}...")
    
    return True

def test_leads_created():
    """Test 6: Lead Creati (tool execution)"""
    print_section("TEST 6: LEAD CREATI OGGI (verifica tool execution)")
    
    today = frappe.utils.today()
    
    leads = frappe.get_all(
        "CRM Lead",
        filters={"creation": [">", today]},
        fields=["name", "first_name", "last_name", "email", "creation"],
        order_by="creation desc",
        limit=10
    )
    
    if not leads:
        print("⚠️  Nessun lead creato oggi")
        print("   → Se hai richiesto creazione lead, il tool NON è stato eseguito!")
        return False
    
    print(f"✅ {len(leads)} lead creati oggi:")
    for lead in leads:
        print(f"   - {lead.name}: {lead.first_name} {lead.last_name} ({lead.email})")
    
    return True

# ====================
# ESEGUI TUTTI I TEST
# ====================

def run_all_tests():
    """Esegui tutti i test"""
    print("\n" + "🔬 "* 20)
    print("AI MODULE - SYSTEM HEALTH CHECK")
    print("🔬 " * 20)
    
    results = {
        "OpenAI Connection": test_openai_connection(),
        "AI Configuration": test_ai_configuration(),
        "Session Files": test_session_files(),
        "Recent Errors": test_recent_errors(),
        "WhatsApp Messages": test_whatsapp_messages(),
        "Leads Created": test_leads_created(),
    }
    
    # Summary
    print_section("📊 RIEPILOGO")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n🎯 Risultato: {passed}/{total} test passati")
    
    if passed == total:
        print("\n🎉 Sistema funzionante correttamente!")
    else:
        print("\n⚠️  Alcuni problemi rilevati - vedi dettagli sopra")

# Esegui automaticamente
run_all_tests()

