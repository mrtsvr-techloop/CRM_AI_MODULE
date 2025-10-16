# 🌐 Cloud Diagnostics for Frappe Cloud

Quick diagnostics tool for troubleshooting AI Module on Frappe Cloud without console access.

---

## 🚀 Quick Start

### 1. Deploy to Frappe Cloud

```bash
git add -A
git commit -m "feat: add cloud diagnostics"
git push origin develop
```

Then update your app on Frappe Cloud Dashboard.

---

### 2. Open Diagnostics Page

Navigate to:
```
https://YOUR-SITE.frappe.cloud/ai-diagnostics
```

Replace `YOUR-SITE` with your actual Frappe Cloud site name.

---

## 🔍 What It Checks

### ✅ Code Deployed
- Verifies if latest code changes are deployed
- Checks for critical function signatures in `threads.py`
- Status: `fail` means you need to redeploy

### ✅ API Key
- Confirms OpenAI API key is configured
- Shows first/last characters for verification
- Status: `fail` means key is missing → check AI Assistant Settings

### ✅ Settings
- AutoReply status (`wa_enable_autoreply`)
- Inline mode (`wa_force_inline`)
- Human cooldown timer
- Status: `warning` if AutoReply is disabled

### ✅ Session Files
- Counts active AI sessions
- Shows conversation persistence status
- Status: `pass` always (informational)

### ✅ WhatsApp Messages
- Incoming/outgoing message counts (last 24h)
- Identifies one-way communication issues
- Status: `fail` if messages received but no responses

### ✅ Recent Errors
- Last 3 errors from AI Module (2h window)
- Shows error type and timestamp
- Status: `fail` if errors exist

---

## 🎯 Common Issues & Fixes

### Problem: "Code Deployed: FAIL"
**Fix**: Redeploy app on Frappe Cloud Dashboard

### Problem: "API Key: FAIL"
**Fix**: 
1. Go to **AI Assistant Settings**
2. Enable "Use Settings Override"
3. Enter your OpenAI API key
4. Save

### Problem: "AutoReply: DISABLED"
**Fix**:
1. Go to **AI Assistant Settings**
2. Enable "WhatsApp AutoReply"
3. Save

### Problem: "Messages received but NO responses"
**Fix**: Check **Recent Errors** section for specific error

---

## 🔄 Reset Sessions

If conversations are stuck or corrupted:

1. Click **"Reset Sessions"** button on diagnostics page
2. Confirm action
3. All AI conversation history will be cleared
4. Next message will start a fresh conversation

---

## 📡 API Access (Advanced)

### Get Diagnostics (JSON)
```bash
curl https://YOUR-SITE.frappe.cloud/api/method/ai_module.api.run_diagnostics \
  -H "Authorization: token API_KEY:API_SECRET"
```

### Reset Sessions (JSON)
```bash
curl -X POST https://YOUR-SITE.frappe.cloud/api/method/ai_module.api.reset_sessions \
  -H "Authorization: token API_KEY:API_SECRET"
```

---

## 🆘 Still Not Working?

1. **Check Frappe Cloud Logs**:
   - Dashboard → Your Site → Logs
   - Filter by "ai_module"

2. **Verify WhatsApp Integration**:
   - Check CRM WhatsApp settings
   - Verify Facebook API credentials

3. **Test with Simple Message**:
   - Send "ciao" to your WhatsApp number
   - Check if response is generated

---

## 🔗 Related Docs

- [Main README](README.md)
- [Responses API Migration](MIGRATION.md)
- [Tool Calling Guide](RESPONSES_API_TOOL_CALLING.md)
- [Local Log Guide](LOG_GUIDE.md)

---

**Last Updated**: 2025-01-16

