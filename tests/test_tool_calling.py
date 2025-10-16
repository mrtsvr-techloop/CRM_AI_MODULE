"""
AI Module - Tool Calling Test

Test specifico per verificare che il tool calling funzioni correttamente.

COME USARE:
    bench console
    >>> exec(open('apps/ai_module/tests/test_tool_calling.py').read())
"""
import frappe
import json
from openai import OpenAI

def print_section(title):
    print("\n" + "="*70)
    print(f"{title}")
    print("="*70)

def test_tool_calling_flow():
    """Test completo del flusso tool calling"""
    print_section("TEST TOOL CALLING - Responses API")
    
    try:
        from ai_module.agents.config import apply_environment, get_environment
        
        apply_environment()
        env = get_environment()
        client = OpenAI(api_key=env["OPENAI_API_KEY"])
        
        # Tool definition (formato Responses API)
        tools = [{
            "type": "function",
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                },
                "required": ["message"]
            }
        }]
        
        # ========================================
        # TEST 1: Prima chiamata (genera tool call)
        # ========================================
        print("\n📋 Step 1: Prima chiamata (dovrebbe generare tool call)...")
        
        resp1 = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "user", "content": [{"type": "input_text", "text": "Usa il tool test_tool con message='hello'"}]}
            ],
            tools=tools
        )
        
        print(f"   Response ID: {resp1.id}")
        print(f"   Output type: {type(resp1.output)}")
        
        # Verifica tool call
        function_calls = [item for item in resp1.output if item.type == "function_call"]
        
        if not function_calls:
            print("   ❌ FAIL: AI non ha chiamato il tool")
            print("   Output ricevuto:")
            for item in resp1.output:
                print(f"      - Type: {item.type}")
            return False
        
        print(f"   ✅ Tool chiamato: {len(function_calls)} function calls")
        
        for fc in function_calls:
            print(f"      - Name: {fc.name}")
            print(f"      - Call ID: {fc.call_id}")
            print(f"      - Arguments: {fc.arguments}")
        
        # ========================================
        # TEST 2: Seconda chiamata (con tool result)
        # ========================================
        print("\n📋 Step 2: Seconda chiamata (con tool result)...")
        
        tool_result = {"success": True, "message": "Tool executed"}
        
        # METODO CORRETTO: Tool result come user message
        resp2 = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "user", "content": [{"type": "input_text", "text": "Usa il tool test_tool con message='hello'"}]},
                {"role": "user", "content": [{"type": "input_text", "text": f"Function test_tool returned: {json.dumps(tool_result)}"}]}
            ],
            tools=tools
            # IMPORTANTE: NON usare previous_response_id=resp1.id
        )
        
        print(f"   Response ID: {resp2.id}")
        
        # Verifica risposta
        messages = [item for item in resp2.output if item.type == "message"]
        
        if not messages:
            print("   ❌ FAIL: Nessun messaggio di risposta")
            return False
        
        print(f"   ✅ Risposta generata:")
        for msg in messages:
            for content in msg.content:
                if hasattr(content, 'text'):
                    print(f"      {content.text[:100]}")
        
        # ========================================
        # TEST 3: Continuità conversazione
        # ========================================
        print("\n📋 Step 3: Continuità conversazione (con previous_response_id)...")
        
        # Ora USO previous_response_id (della risposta completa, non quella con tool call)
        resp3 = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "user", "content": [{"type": "input_text", "text": "Grazie!"}]}
            ],
            previous_response_id=resp2.id  # ✅ OK: response completo
        )
        
        print(f"   Response ID: {resp3.id}")
        print(f"   ✅ Continuità conversazione OK")
        
        print("\n" + "="*70)
        print("🎉 TUTTI I TEST PASSATI!")
        print("="*70)
        print("\n✅ Il tool calling funziona correttamente!")
        print("✅ Il flusso è:")
        print("   1. Prima chiamata → AI chiama tool")
        print("   2. Seconda chiamata (tool result come user message, NO prev_id)")
        print("   3. Terza chiamata (continuità conversazione, CON prev_id della risposta completa)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        import traceback
        print("\nTraceback:")
        print(traceback.format_exc())
        return False

def test_wrong_method():
    """Test metodo sbagliato (per confronto)"""
    print_section("TEST METODO SBAGLIATO (dovrebbe fallire)")
    
    try:
        from ai_module.agents.config import apply_environment, get_environment
        
        apply_environment()
        env = get_environment()
        client = OpenAI(api_key=env["OPENAI_API_KEY"])
        
        tools = [{
            "type": "function",
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                },
                "required": ["message"]
            }
        }]
        
        # Prima chiamata
        resp1 = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "user", "content": [{"type": "input_text", "text": "Usa test_tool"}]}
            ],
            tools=tools
        )
        
        function_calls = [item for item in resp1.output if item.type == "function_call"]
        if not function_calls:
            print("   ⚠️  AI non ha chiamato tool, test inconcludente")
            return
        
        # METODO SBAGLIATO: Usa previous_response_id nel tool calling loop
        print("\n   Tentativo con previous_response_id (SBAGLIATO)...")
        try:
            resp2 = client.responses.create(
                model="gpt-4o-mini",
                input=[
                    {"role": "user", "content": [{"type": "input_text", "text": "Function test_tool returned: {}"}]}
                ],
                tools=tools,
                previous_response_id=resp1.id  # ❌ QUESTO CAUSA L'ERRORE
            )
            print("   ⚠️  Inaspettato: non ha dato errore (forse OpenAI ha fixato?)")
        except Exception as e:
            if "No tool output found" in str(e):
                print(f"   ✅ Errore atteso ricevuto: 'No tool output found'")
                print("   → Questo conferma che NON si deve usare previous_response_id")
            else:
                print(f"   ❌ Errore diverso: {e}")
        
    except Exception as e:
        print(f"   ❌ Errore setup: {e}")

# ====================
# ESEGUI TEST
# ====================

print("\n" + "🔬 "* 20)
print("AI MODULE - TOOL CALLING TEST")
print("🔬 " * 20)

# Test 1: Metodo corretto
success = test_tool_calling_flow()

# Test 2: Metodo sbagliato (per educazione)
test_wrong_method()

# Summary
print("\n" + "="*70)
if success:
    print("✅ TOOL CALLING VERIFICATO E FUNZIONANTE")
else:
    print("❌ PROBLEMI CON TOOL CALLING - Vedi dettagli sopra")
print("="*70)

