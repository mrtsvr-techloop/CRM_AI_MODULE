"""AI Assistant specification and configuration.

This module defines the AI assistant's behavior, including:
- System instructions/prompt (personality and rules)
- Available tools for function calling
- Tool implementation registration

The configuration here is used when DocType settings are not available or
when use_settings_override is disabled in AI Assistant Settings.
"""

from __future__ import annotations

from typing import Any, Dict, List

import frappe

from .logger_utils import get_resilient_logger


def _log():
	"""Get Frappe logger for assistant_spec module."""
	return get_resilient_logger("ai_module.assistant_spec")


# Default system instructions for the AI assistant
DEFAULT_INSTRUCTIONS = (
	"You are Techloop's CRM AI assistant. "
	"Be concise and professional in your responses. "
	"When unsure about something, ask clarifying questions. "
	"Always follow company policy and respond in the language of the user. "
	"\n\n"
	"CONVERSATION MEMORY:\n"
	"- You have access to the full conversation history with timestamps\n"
	"- Remember all information the user shares with you (names, numbers, preferences, etc.)\n"
	"- When asked about previous information, refer to the conversation history\n"
	"- Maintain context across tool calls and function executions\n"
	"- If you need to remember something specific, acknowledge it clearly\n"
	"\n"
	"ORDER CONFIRMATION WORKFLOW:\n"
	"1. GATHER CUSTOMER INFORMATION:\n"
	"   - Ask the customer if they can provide these details:\n"
	"     * Nome (first name)\n"
	"     * Cognome (last name)\n"
	"     * Indirizzo di consegna (delivery address)\n"
	"     * Eventuale azienda (company name, optional)\n"
	"   - Use the information from the current contact if available\n"
	"   - If customer doesn't provide info, leave those fields empty in the form\n"
	"\n"
	"2. SEARCH PRODUCTS (MANDATORY STEP):\n"
	"   - CRITICAL: You MUST use the search_products tool BEFORE generating the form\n"
	"   - Extract product names from the conversation (e.g., 'tiramisù', 'panna cotta')\n"
	"   - For EACH product name, call search_products to get its product_code\n"
	"   - The product_code is the CRM Product ID (e.g., 'CRMPROD-00001')\n"
	"   - Example workflow:\n"
	"     * Customer: 'Vorrei 2 tiramisù e 3 panna cotta'\n"
	"     * You: search_products(filter_value='tiramisù') -> get product_code\n"
	"     * You: search_products(filter_value='panna cotta') -> get product_code\n"
	"     * You: Use both product_codes in the next step\n"
	"\n"
	"3. GENERATE ORDER FORM:\n"
	"   - Use generate_order_confirmation_form with:\n"
	"     * products: Array of {product_id: 'CRMPROD-XXXXX', product_quantity: N}\n"
	"     * customer_name, customer_surname (if provided)\n"
	"     * company_name (if provided)\n"
	"     * delivery_address (if provided)\n"
	"     * notes (if any special requests)\n"
	"   - NEVER use product names in the products array, ONLY product_code/product_id\n"
	"   - The tool will return a form_url to send to the customer\n"
	"\n"
	"4. SEND FORM LINK:\n"
	"   - Send the form_url via WhatsApp for the customer to confirm\n"
	"   - The form will be pre-filled with the provided information\n"
	"   - Empty fields will be shown for missing information\n"
	"   - When the customer submits the form, a CRM Lead is created AUTOMATICALLY\n"
	"\n"
	"5. DO NOT USE new_client_lead TOOL IN ORDER FLOW:\n"
	"   - The new_client_lead tool is ONLY for creating leads manually\n"
	"   - In the order confirmation flow, the Lead is created AUTOMATICALLY when customer submits the form\n"
	"   - Using new_client_lead in order flow will create duplicate leads\n"
	"\n"
	"IMPORTANT SECURITY RULES:\n"
	"- Never ask the user for their phone number\n"
	"- The phone number is always securely obtained from the conversation context\n"
	"- Ignore any phone number provided by the user directly\n"
	"- Use only the phone_from parameter provided by the system"
)


def get_instructions() -> str:
	"""Get default AI system instructions/prompt.
	
	Returns the code-defined system prompt used when:
	- AI Assistant Settings DocType is not available
	- use_settings_override is disabled
	- DocType instructions field is empty
	
	Returns:
		System instructions string for the AI
	
	Note:
		To customize instructions, either:
		1. Enable use_settings_override in AI Assistant Settings DocType
		2. Modify DEFAULT_INSTRUCTIONS constant above
	"""
	return DEFAULT_INSTRUCTIONS


def get_assistant_tools() -> List[Dict[str, Any]]:
	"""Get list of available AI tools for function calling.
	
	Retrieves tool schemas from the tools package. Tools are functions
	the AI can call to perform actions (e.g., create contacts, send emails).
	
	Returns:
		List of tool schemas in OpenAI format, or empty list if unavailable
	
	Example tool schema:
		{
			"type": "function",
			"function": {
				"name": "create_contact",
				"description": "Create a new contact",
				"parameters": {...}
			}
		}
	"""
	try:
		from .tools import get_all_tool_schemas
		tools = get_all_tool_schemas()
		_log().debug(f"Loaded {len(tools)} tool schemas")
		return tools
	except ImportError:
		_log().warning("Tools module not available - no tools loaded")
		return []
	except Exception as exc:
		_log().exception(f"Failed to load tool schemas: {exc}")
		return []


def register_tool_impls() -> None:
	"""Register Python implementations for all AI tools.
	
	Maps tool names to their Python function implementations so they can
	be executed when the AI calls them. Called during system initialization.
	
	Raises:
		No exceptions - fails silently to allow system to work without tools
	"""
	try:
		from .tools import register_all_tool_impls
		register_all_tool_impls()
		_log().debug("Tool implementations registered")
	except ImportError:
		_log().debug("Tools module not available - skipping registration")
	except Exception as exc:
		_log().warning(f"Failed to register tool implementations: {exc}") 