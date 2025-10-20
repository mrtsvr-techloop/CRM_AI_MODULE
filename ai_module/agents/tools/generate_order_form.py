from __future__ import annotations

from typing import Any, Dict, Optional

SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_order_confirmation_form",
        "description": (
            "Generate a WhatsApp order confirmation form link with pre-filled data. "
            "This creates a secure form that customers can fill to confirm their order. "
            "The form is pre-populated with the order details extracted from the conversation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's full name"
                },
                "phone_number": {
                    "type": "string", 
                    "description": "Customer's phone number (same as WhatsApp number)"
                },
                "product_name": {
                    "type": "string",
                    "description": "Name of the product/service ordered"
                },
                "quantity": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Quantity of the product"
                },
                "unit_price": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Price per unit in euros"
                },
                "delivery_address": {
                    "type": "string",
                    "description": "Customer's delivery address"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes or special instructions"
                }
            },
            "required": ["customer_name", "phone_number", "product_name", "quantity"]
        },
    },
}

def generate_order_confirmation_form(**kwargs) -> Dict[str, Any]:
    """Generate a WhatsApp order confirmation form link with pre-filled data.
    
    This function creates a secure form URL that customers can use to confirm their order.
    The form is pre-populated with the order details extracted from the conversation.
    
    Args:
        customer_name: Customer's full name
        phone_number: Customer's phone number (same as WhatsApp number)
        product_name: Name of the product/service ordered
        quantity: Quantity of the product
        unit_price: Price per unit in euros (optional)
        delivery_address: Customer's delivery address (optional)
        notes: Additional notes or special instructions (optional)
    
    Returns:
        {
            "success": bool,
            "form_url": str,  # Pre-filled form URL
            "message": str,
            "order_summary": {
                "customer_name": str,
                "product_name": str,
                "quantity": int,
                "total_price": float
            }
        }
    """
    try:
        # Validate required parameters
        required_params = ["customer_name", "phone_number", "product_name", "quantity"]
        for param in required_params:
            if not kwargs.get(param):
                return {
                    "success": False,
                    "error": f"Missing required parameter: {param}"
                }
        
        # Calculate total price
        quantity = int(kwargs.get("quantity", 1))
        unit_price = float(kwargs.get("unit_price", 0))
        total_price = quantity * unit_price
        
        # Build form URL with pre-filled parameters (CRM endpoint)
        # Prefer absolute URL using Frappe site base when available
        try:
            import frappe  # type: ignore
            from frappe.utils import get_url  # type: ignore
            base_url = get_url("/crm/order_confirmation")  # absolute URL
        except Exception:
            # Fallback: relative path if frappe context not available
            base_url = "/crm/order_confirmation"

        params = {
            "customer_name": kwargs.get("customer_name"),
            "phone_number": kwargs.get("phone_number"),
            "product_name": kwargs.get("product_name"),
            "quantity": str(quantity),
            "unit_price": str(unit_price),
            "total_price": str(total_price),
            "delivery_address": kwargs.get("delivery_address", ""),
            "notes": kwargs.get("notes", "")
        }
        
        # Create URL-encoded query string
        try:
            from urllib.parse import urlencode, quote_plus
            query_string = urlencode({k: v for k, v in params.items() if v}, quote_via=quote_plus)
        except Exception:
            # Very defensive fallback (no spaces encoded properly)
            query_string = "&".join([f"{k}={str(v)}" for k, v in params.items() if v])
        form_url = f"{base_url}?{query_string}"
        
        # Create order summary
        order_summary = {
            "customer_name": kwargs.get("customer_name"),
            "product_name": kwargs.get("product_name"),
            "quantity": quantity,
            "total_price": total_price
        }
        
        return {
            "success": True,
            "form_url": form_url,
            "message": f"Form di conferma ordine generato per {kwargs.get('customer_name')}",
            "order_summary": order_summary
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating form: {str(e)}"
        }

IMPL_FUNC = generate_order_confirmation_form
