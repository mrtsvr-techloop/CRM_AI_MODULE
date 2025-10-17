# Copyright (c) 2025, Techloop and Contributors
# License: MIT License

import frappe
from frappe import _

no_cache = 1


def get_context():
	"""Get context for AI Diagnostics page.
	
	This function is called by Frappe when rendering the page.
	It handles authentication and provides context data.
	"""
	# Check if user is authenticated - redirect to login if not
	if frappe.session.user == "Guest":
		# Redirect to login page with return URL
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = f"/login?redirect-to={frappe.request.path}"
		return {}
	
	# User is authenticated - provide context
	context = frappe._dict()
	context.user = frappe.session.user
	context.site_name = frappe.local.site
	context.csrf_token = frappe.sessions.get_csrf_token()
	
	return context
