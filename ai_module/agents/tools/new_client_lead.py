from __future__ import annotations

from typing import Any, Dict

SCHEMA: Dict[str, Any] = {
	"type": "function",
	"function": {
		"name": "new_client_lead",
		"description": (
			"Create a new CRM Lead. Required: first_name, last_name, email, organization. "
			"Never ask the user for a phone number. The phone is securely obtained from the conversation thread context and any user-provided numbers must be ignored. "
			"Optional: website, territory, industry, source."
		),
		"parameters": {
			"type": "object",
			"properties": {
				"first_name": {"type": "string"},
				"last_name": {"type": "string"},
				"email": {"type": "string", "format": "email"},
				"organization": {"type": "string"},
				"reference_doctype": {"type": "string"},
				"reference_name": {"type": "string"},
				"website": {"type": "string"},
				"territory": {"type": "string"},
				"industry": {"type": "string"},
				"source": {"type": "string"},
			},
			"required": [
				"first_name",
				"last_name",
				"organization",
			],
		},
	},
}

# Direct implementation wrapper: import and delegate at call-time (avoids import-order issues)

def new_client_lead(**kwargs) -> Dict[str, Any]:
	# Security: NEVER use user-provided mobile_no. Always source from thread context.
	# Remove any incoming mobile_no to avoid accidental use.
	kwargs.pop("mobile_no", None)
	# Always prefer the WhatsApp-originating number if provided by the agent context
	phone_from = (kwargs.get("phone_from") or "").strip()
	if phone_from:
		kwargs["mobile_no"] = phone_from
	from crm.api.workflow import new_client_lead as _impl
	return _impl(**kwargs)

# Register callable implementation immediately during discovery
IMPL_FUNC = new_client_lead