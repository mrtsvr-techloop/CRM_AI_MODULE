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
