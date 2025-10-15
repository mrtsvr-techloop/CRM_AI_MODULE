from __future__ import annotations

from typing import Any, Dict


# Assistant Tool Schema: update_contact
# - Purpose: Update or create the Contact tied to the current thread phone
# - Required: first_name, last_name
# - Optional: email, organization, confirm_organization, phone_from (injected)

SCHEMA: Dict[str, Any] = {
	"type": "function",
	"function": {
		"name": "update_contact",
		"description": (
			"Update (or create) the Contact for this conversation. "
			"Required: first_name, last_name. Optional: email, organization, confirm_organization (boolean). "
			"Never ask the user for a phone number: it is always taken from the thread context and injected as phone_from."
		),
		"parameters": {
			"type": "object",
			"properties": {
				"first_name": {"type": "string"},
				"last_name": {"type": "string"},
				"email": {"type": "string", "format": "email"},
				"organization": {"type": "string"},
				"confirm_organization": {"type": "boolean"},
				"phone_from": {"type": "string"},
			},
			"required": [
				"first_name",
				"last_name",
			],
		},
	},
}


def update_contact(**kwargs) -> Dict[str, Any]:
	# Pass-through to CRM workflow; phone_from is injected by the executor
	from crm.api.workflow import update_contact_from_thread as _impl
	return _impl(**kwargs)


# Register callable implementation immediately during discovery
IMPL_FUNC = update_contact


