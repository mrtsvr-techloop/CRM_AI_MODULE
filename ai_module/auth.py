"""
AI Module Authentication Hooks

Handles authentication and authorization for AI Module pages and endpoints.
"""

import frappe


def validate_page_access():
	"""Validate access to AI Module pages.
	
	This hook is called for every request to AI Module pages.
	Redirects to login if user is not authenticated.
	"""
	# Only apply to AI Module pages
	if not frappe.request.path.startswith('/ai-diagnostics'):
		return
	
	# Check if user is authenticated
	if frappe.session.user == "Guest":
		# Redirect to login with return URL
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = f"/login?redirect-to={frappe.request.path}"
		return
	
	# User is authenticated - allow access
	return


def validate_api_access():
	"""Validate access to AI Module API endpoints.
	
	This is called for API requests to ensure proper authentication.
	"""
	# Only apply to AI Module API endpoints
	if not frappe.request.path.startswith('/api/method/ai_module.'):
		return
	
	# Check if user is authenticated
	if frappe.session.user == "Guest":
		frappe.throw("Authentication required", frappe.PermissionError)
	
	# User is authenticated - allow access
	return
