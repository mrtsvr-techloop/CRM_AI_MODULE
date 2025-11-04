from __future__ import annotations

from typing import Any, Dict, Optional

SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_order_confirmation_form",
        "description": (
            "Generate a WhatsApp order confirmation form link with pre-filled customer and order data. "
            "CRITICAL: Before calling this tool, you MUST use search_products to get product_code for each product. "
            "The products parameter requires product_id (which is the product_code from search_products), NOT product names. "
            "Example: search_products(filter_value='tiramisù') returns product_code='CRMPROD-00001', then use "
            "products=[{product_id: 'CRMPROD-00001', product_quantity: 2}]. "
            "This creates a secure FCRM TEMP ORDINE record that customers can access to confirm their order. "
            "When the customer submits the form, a CRM Lead is created AUTOMATICALLY - do NOT use new_client_lead tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's first name (extracted from conversation)"
                },
                "customer_surname": {
                    "type": "string",
                    "description": "Customer's last name/surname (extracted from conversation)"
                },
                "company_name": {
                    "type": "string",
                    "description": "Customer's company name (optional, extracted from conversation)"
                },
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "CRM Product code/ID obtained from search_products tool (e.g., 'CRMPROD-00001'). NEVER use product name here."
                            },
                            "product_quantity": {
                                "type": "integer",
                                "minimum": 1,
                                "description": "Quantity of this product requested by the customer"
                            }
                        },
                        "required": ["product_id", "product_quantity"]
                    },
                    "description": "Array of products with their CRM Product codes (from search_products) and quantities. Must contain at least one product."
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
            "required": ["products"]
        },
    },
}

def generate_order_confirmation_form(**kwargs) -> Dict[str, Any]:
    """Generate a WhatsApp order confirmation form link with pre-filled data.
    
    This function creates a secure FCRM TEMP ORDINE record that customers can use to confirm their order.
    The form is pre-populated with the order details extracted from the conversation.
    
    Args:
        customer_name: Customer's first name (extracted from conversation, optional)
        customer_surname: Customer's last name/surname (extracted from conversation, optional)
        company_name: Customer's company name (optional, extracted from conversation)
        phone_from: Customer's phone number (automatically injected by security system)
        products: Array of products with product_id and product_quantity
        delivery_address: Customer's delivery address (optional)
        notes: Additional notes or special instructions (optional)
    
    Returns:
        {
            "success": bool,
            "form_url": str,  # Short URL to FCRM TEMP ORDINE
            "message": str,
            "order_summary": {
                "customer_name": str,
                "products_count": int,
                "temp_order_id": str
            }
        }
    """
    try:
        # Get phone_from (automatically injected by security system)
        phone_from = kwargs.get("phone_from")
        if not phone_from:
            return {
                "success": False,
                "error": "Phone number not available from conversation context"
            }
        
        # Use phone_from as the phone_number
        phone_number = phone_from
        
        # Get customer_name from kwargs (should be extracted by AI from conversation)
        customer_name = kwargs.get("customer_name", "")
        customer_surname = kwargs.get("customer_surname", "")
        company_name = kwargs.get("company_name", "")
        
        # Validate required parameters
        required_params = ["products"]
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
        
        # CRITICAL: Validate that all product_id values exist in the database
        # This forces the AI to use search_products to get real product codes
        try:
            import frappe
            invalid_products = []
            
            for i, product in enumerate(products):
                product_id = product.get("product_id")
                
                # Check if product exists in CRM Product
                exists = frappe.db.exists("CRM Product", product_id)
                if not exists:
                    invalid_products.append({
                        "index": i + 1,
                        "product_id": product_id
                    })
            
            if invalid_products:
                error_details = ", ".join([
                    f"Product {p['index']} (ID: {p['product_id']})" 
                    for p in invalid_products
                ])
                return {
                    "success": False,
                    "error": (
                        f"Invalid product_id detected: {error_details}. "
                        f"CRITICAL: You MUST use the search_products tool to get valid product codes from the database. "
                        f"NEVER invent or guess product IDs. "
                        f"Example: search_products(filter_value='product_name') will return valid product_code values."
                    )
                }
        except Exception as validation_error:
            return {
                "success": False,
                "error": f"Error validating products: {str(validation_error)}"
            }
        
        # Create FCRM TEMP ORDINE record
        try:
            import frappe
            import time
            import json
            
            # Prepare order data
            current_time = int(time.time())
            expires_at = current_time + 300  # 5 minutes
            
            order_data = {
                "customer_name": customer_name,
                "customer_surname": customer_surname,
                "phone_number": phone_number,
                "company_name": company_name,
                "products": products,
                "delivery_address": kwargs.get("delivery_address", ""),
                "notes": kwargs.get("notes", "")
            }
            
            # Create FCRM TEMP ORDINE record
            temp_order_doc = frappe.get_doc({
                "doctype": "FCRM TEMP ORDINE",
                "content": json.dumps(order_data),
                "created_at": current_time,
                "expires_at": expires_at,
                "status": "Active"
            })
            
            temp_order_doc.insert(ignore_permissions=True)
            frappe.db.commit()  # Force commit to ensure data is saved
            temp_order_id = temp_order_doc.name
            
            # Build form URL using FCRM TEMP ORDINE ID as query parameter
            try:
                from frappe.utils import get_url
                form_url = get_url(f"/order_confirmation?order_id={temp_order_id}")
            except Exception:
                form_url = f"/order_confirmation?order_id={temp_order_id}"
            
            # Create order summary
            customer_full_name = f"{customer_name} {customer_surname}".strip() if customer_name or customer_surname else "Cliente"
            order_summary = {
                "customer_name": customer_full_name,
                "products_count": len(products),
                "temp_order_id": temp_order_id
            }
            
            return {
                "success": True,
                "form_url": form_url,
                "message": f"Form di conferma ordine generato per {customer_full_name}",
                "order_summary": order_summary
            }
            
        except Exception as frappe_error:
            return {
                "success": False,
                "error": f"Error creating FCRM TEMP ORDINE: {str(frappe_error)}"
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating form: {str(e)}"
        }

IMPL_FUNC = generate_order_confirmation_form
