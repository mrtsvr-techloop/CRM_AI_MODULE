# Copyright (c) 2025, Techloop and Contributors
# License: MIT License

import frappe
from frappe import _

no_cache = 1


def get_context():
	context = frappe._dict()
	context.user = frappe.session.user
	context.site_name = frappe.local.site
	return context


@frappe.whitelist(allow_guest=False)
def search_conversation(phone_number):
	"""JavaScript callable function to search conversation."""
	from ai_module.api import get_conversation_memory
	return get_conversation_memory(phone_number)


@frappe.whitelist(allow_guest=False)
def list_conversations():
	"""JavaScript callable function to list all conversations."""
	from ai_module.api import list_all_conversations
	return list_all_conversations()
