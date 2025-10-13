from __future__ import annotations

from typing import Any, Dict

SCHEMA: Dict[str, Any] = {
	"type": "function",
	"function": {
		"name": "new_client_lead",
		"description": (
			"Create a new CRM Lead. Required: first_name, last_name, email, mobile_no, organization. "
			"Optional: website, territory, industry, source."
		),
		"parameters": {
			"type": "object",
			"properties": {
				"first_name": {"type": "string"},
				"last_name": {"type": "string"},
				"email": {"type": "string", "format": "email"},
				"mobile_no": {"type": "string"},
				"organization": {"type": "string"},
				"website": {"type": "string"},
				"territory": {"type": "string"},
				"industry": {"type": "string"},
				"source": {"type": "string"},
			},
			"required": [
				"first_name",
				"last_name",
				"email",
				"mobile_no",
				"organization",
			],
		},
	},
}

# Direct implementation wrapper: import and delegate at call-time (avoids import-order issues)
def new_client_lead(**kwargs) -> Dict[str, Any]:
	from crm.api.workflow import new_client_lead as _impl
	return _impl(**kwargs)

# Register callable implementation immediately during discovery
IMPL_FUNC = new_client_lead