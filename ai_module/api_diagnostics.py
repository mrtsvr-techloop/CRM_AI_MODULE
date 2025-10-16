"""
AI Module - Diagnostics API

Endpoint per diagnostica su Frappe Cloud (senza console access).

COME USARE:
    GET https://your-site.frappe.cloud/api/method/ai_module.ai_module.api_diagnostics.run_diagnostics
    
    Oppure dal browser:
    https://your-site.frappe.cloud/app/ai-diagnostics
"""
import frappe
import json
import os
from frappe import _


@frappe.whitelist(allow_guest=False)
def run_diagnostics():
    """Run system diagnostics and return results."""
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required", frappe.PermissionError)
    
    results = {
        "timestamp": frappe.utils.now(),
        "site": frappe.local.site,
        "tests": {}
    }
    
    # Test 1: Code deployed
    try:
        from ai_module.agents import threads
        import inspect
        source = inspect.getsource(threads.run_with_responses_api)
        
        checks = {
            "has_function_call": "FUNCTION_CALL" in source or "function_call" in source,
            "has_iteration_check": "iteration == 1" in source,
            "has_user_role": 'role": "user"' in source or "role: \"user\"" in source
        }
        
        results["tests"]["code_deployed"] = {
            "status": "pass" if all(checks.values()) else "fail",
            "details": checks,
            "message": "Code updated" if all(checks.values()) else "Old code - redeploy needed"
        }
    except Exception as e:
        results["tests"]["code_deployed"] = {
            "status": "error",
            "message": str(e)
        }
    
    # Test 2: API Key
    try:
        from ai_module.agents.config import apply_environment, get_environment
        apply_environment()
        env = get_environment()
        api_key = env.get("OPENAI_API_KEY")
        
        results["tests"]["api_key"] = {
            "status": "pass" if api_key else "fail",
            "message": f"Present ({api_key[:10]}...{api_key[-4:]})" if api_key else "Not configured",
            "has_key": bool(api_key)
        }
    except Exception as e:
        results["tests"]["api_key"] = {
            "status": "error",
            "message": str(e)
        }
    
    # Test 3: Settings
    try:
        settings = frappe.get_single("AI Assistant Settings")
        results["tests"]["settings"] = {
            "status": "pass" if settings.wa_enable_autoreply else "warning",
            "autoreply": bool(settings.wa_enable_autoreply),
            "inline": bool(settings.wa_force_inline),
            "cooldown": settings.wa_human_cooldown_seconds,
            "message": "AutoReply enabled" if settings.wa_enable_autoreply else "AutoReply DISABLED"
        }
    except Exception as e:
        results["tests"]["settings"] = {
            "status": "error",
            "message": str(e)
        }
    
    # Test 4: Session files
    try:
        site_path = frappe.utils.get_site_path()
        files_dir = os.path.join(site_path, "private", "files")
        
        response_file = os.path.join(files_dir, "ai_whatsapp_responses.json")
        sessions_count = 0
        
        if os.path.exists(response_file):
            with open(response_file, "r") as f:
                content = f.read().strip()
            if content:
                data = json.loads(content)
                sessions_count = len(data)
        
        results["tests"]["session_files"] = {
            "status": "pass",
            "sessions": sessions_count,
            "message": f"{sessions_count} active sessions"
        }
    except Exception as e:
        results["tests"]["session_files"] = {
            "status": "error",
            "message": str(e)
        }
    
    # Test 5: Recent messages
    try:
        yesterday = frappe.utils.add_to_date(frappe.utils.now(), days=-1)
        messages = frappe.get_all(
            "WhatsApp Message",
            filters={"creation": [">", yesterday]},
            fields=["name", "type", "creation"],
            order_by="creation desc",
            limit=20
        )
        
        incoming = [m for m in messages if m.type == "Incoming"]
        outgoing = [m for m in messages if m.type == "Outgoing"]
        
        status = "pass"
        if incoming and not outgoing:
            status = "fail"
            message = "Messages received but NO responses sent"
        elif not incoming:
            status = "warning"
            message = "No recent messages"
        else:
            message = f"{len(incoming)} in, {len(outgoing)} out"
        
        results["tests"]["whatsapp_messages"] = {
            "status": status,
            "incoming": len(incoming),
            "outgoing": len(outgoing),
            "message": message
        }
    except Exception as e:
        results["tests"]["whatsapp_messages"] = {
            "status": "error",
            "message": str(e)
        }
    
    # Test 6: Recent errors
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
        
        error_details = []
        for err_info in errors:
            err = frappe.get_doc("Error Log", err_info.name)
            # Extract error type from last lines
            lines = err.error.split('\n')
            error_type = "Unknown"
            for line in reversed(lines[-10:]):
                if 'Error' in line:
                    error_type = line.strip()[:100]
                    break
            
            error_details.append({
                "time": err.creation,
                "method": err.method,
                "error": error_type
            })
        
        results["tests"]["recent_errors"] = {
            "status": "fail" if errors else "pass",
            "count": len(errors),
            "errors": error_details,
            "message": f"{len(errors)} errors in last 2h" if errors else "No recent errors"
        }
    except Exception as e:
        results["tests"]["recent_errors"] = {
            "status": "error",
            "message": str(e)
        }
    
    # Overall status
    test_statuses = [t.get("status") for t in results["tests"].values()]
    if "fail" in test_statuses or "error" in test_statuses:
        results["overall_status"] = "fail"
        results["overall_message"] = "Issues found - see details"
    elif "warning" in test_statuses:
        results["overall_status"] = "warning"
        results["overall_message"] = "System OK with warnings"
    else:
        results["overall_status"] = "pass"
        results["overall_message"] = "All systems operational"
    
    return results


@frappe.whitelist(allow_guest=False)
def reset_sessions():
    """Reset AI WhatsApp sessions."""
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required", frappe.PermissionError)
    
    try:
        site_path = frappe.utils.get_site_path()
        files_dir = os.path.join(site_path, "private", "files")
        
        files_reset = []
        for filename in ["ai_whatsapp_responses.json", "ai_whatsapp_threads.json", "ai_whatsapp_handoffjson"]:
            filepath = os.path.join(files_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, "w") as f:
                    json.dump({}, f)
                files_reset.append(filename)
        
        return {
            "status": "success",
            "message": f"Reset {len(files_reset)} session files",
            "files": files_reset
        }
    except Exception as e:
        frappe.throw(str(e))

