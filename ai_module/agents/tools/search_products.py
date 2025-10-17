from __future__ import annotations

from typing import Any, Dict

SCHEMA: Dict[str, Any] = {
	"type": "function",
	"function": {
		"name": "search_products",
		"description": (
			"Search CRM Products by tag, price, or name. "
			"The AI can automatically detect the filter type or specify it explicitly. "
			"If no filter_value is provided, returns ALL active products. "
			"Returns product name, price, and tags (called 'Etichette' in Italian). "
			"Only returns active products (not disabled)."
		),
		"parameters": {
			"type": "object",
			"properties": {
				"filter_value": {
					"type": "string",
					"description": "The value to search for (tag name, price, or product name). If empty, returns ALL products."
				},
				"filter_type": {
					"type": "string",
					"enum": ["tag", "price", "name"],
					"description": "Optional filter type. If not provided, will auto-detect based on the filter_value"
				},
				"limit": {
					"type": "integer",
					"minimum": 1,
					"maximum": 200,
					"default": 50,
					"description": "Maximum number of results to return (default: 50)"
				}
			},
			"required": [],
		},
	},
}

# Direct implementation wrapper: import and delegate at call-time (avoids import-order issues)

def search_products(**kwargs) -> Dict[str, Any]:
	"""Search CRM Products by tag, price, or name.
	
	This function allows AI agents to search for products using flexible filtering.
	The AI can determine the filter type automatically or specify it explicitly.
	If no filter_value is provided, returns ALL active products.
	
	Args:
		filter_value: Optional value to search for (tag name, price, or product name). If empty, returns ALL products
		filter_type: Optional filter type ("tag", "price", "name"). If None, auto-detects
		limit: Maximum number of results to return (default: 50)
	
	Returns:
		{
			"success": bool,
			"products": [
				{
					"name": str,           # Product name
					"product_code": str,   # Product code
					"standard_rate": float, # Price
					"tags": [str],         # List of tag names (Etichette)
					"description": str,    # Product description
					"disabled": bool        # Is disabled
				}
			],
			"total_found": int,
			"filter_applied": str,
			"message": str
		}
	"""
	# Filter only the arguments that are defined in the schema
	allowed_args = {"filter_value", "filter_type", "limit"}
	filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_args}
	
	from crm.api.workflow import search_products as _impl
	return _impl(**filtered_kwargs)

# Register callable implementation immediately during discovery
IMPL_FUNC = search_products
