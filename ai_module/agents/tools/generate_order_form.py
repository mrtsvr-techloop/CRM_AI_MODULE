from __future__ import annotations

from typing import Any, Dict, Optional

SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_order_confirmation_form",
        "description": (
            "Generate a WhatsApp order confirmation form link with pre-filled data. "
            "This creates a secure Temp_Ordine record that customers can access to confirm their order. "
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
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "CRM Product ID"
                            },
                            "product_quantity": {
                                "type": "integer",
                                "minimum": 1,
                                "description": "Quantity of this product"
                            }
                        },
                        "required": ["product_id", "product_quantity"]
                    },
                    "description": "Array of products with their IDs and quantities"
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
            "required": ["customer_name", "phone_number", "products"]
        },
    },
}

def generate_order_confirmation_form(**kwargs) -> Dict[str, Any]:
    """Generate a WhatsApp order confirmation form link with pre-filled data.
    
    This function creates a secure Temp_Ordine record that customers can use to confirm their order.
    The form is pre-populated with the order details extracted from the conversation.
    
    Args:
        customer_name: Customer's full name
        phone_number: Customer's phone number (same as WhatsApp number)
        products: Array of products with product_id and product_quantity
        delivery_address: Customer's delivery address (optional)
        notes: Additional notes or special instructions (optional)
    
    Returns:
        {
            "success": bool,
            "form_url": str,  # Short URL to Temp_Ordine
            "message": str,
            "order_summary": {
                "customer_name": str,
                "products_count": int,
                "temp_order_id": str
            }
        }
    """
    try:
        # Validate required parameters
        required_params = ["customer_name", "phone_number", "products"]
        for param in required_params:
            if not kwargs.get(param):
                return {
                    "success": False,
                    "error": f"Missing required parameter: {param}"
                }
        
        # Validate products array
        products = kwargs.get("products", [])
        if not isinstance(products, list) or len(products) == 0:
            return {
                "success": False,
                "error": "Products array is required and must not be empty"
            }
        
        # Validate each product has required fields
        for i, product in enumerate(products):
            if not product.get("product_id") or not product.get("product_quantity"):
                return {
                    "success": False,
                    "error": f"Product {i+1} missing product_id or product_quantity"
                }
        
        # Create Temp_Ordine record
        try:
            import frappe
            import time
            import json
            
            # Prepare order data
            current_time = int(time.time())
            expires_at = current_time + 300  # 5 minutes
            
            order_data = {
                "customer_name": kwargs.get("customer_name"),
                "phone_number": kwargs.get("phone_number"),
                "products": products,
                "delivery_address": kwargs.get("delivery_address", ""),
                "notes": kwargs.get("notes", "")
            }
            
            # Create Temp_Ordine record
            temp_order_doc = frappe.get_doc({
                "doctype": "Temp_Ordine",
                "order_data": json.dumps(order_data),
                "created_at": current_time,
                "expires_at": expires_at,
                "status": "Active"
            })
            
            temp_order_doc.insert(ignore_permissions=True)
            temp_order_id = temp_order_doc.name
            
            # Build form URL using Temp_Ordine ID
            try:
                from frappe.utils import get_url
                form_url = get_url(f"/order_confirmation/{temp_order_id}")
            except Exception:
                form_url = f"/order_confirmation/{temp_order_id}"
            
            # Create order summary
            order_summary = {
                "customer_name": kwargs.get("customer_name"),
                "products_count": len(products),
                "temp_order_id": temp_order_id
            }
            
            return {
                "success": True,
                "form_url": form_url,
                "message": f"Form di conferma ordine generato per {kwargs.get('customer_name')}",
                "order_summary": order_summary
            }
            
        except Exception as frappe_error:
            return {
                "success": False,
                "error": f"Error creating Temp_Ordine: {str(frappe_error)}"
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating form: {str(e)}"
        }

IMPL_FUNC = generate_order_confirmation_form
