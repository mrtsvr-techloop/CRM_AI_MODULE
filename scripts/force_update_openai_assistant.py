#!/usr/bin/env python3
"""Script to force update OpenAI Assistant with current settings.

Usage:
    bench execute ai_module.scripts.force_update_openai_assistant.force_update_assistant
"""

import frappe


def force_update_assistant():
	"""Force update OpenAI Assistant with current settings from AI Assistant Settings."""
	
	print("=" * 60)
	print("Force Update OpenAI Assistant")
	print("=" * 60)
	
	# Get settings
	settings = frappe.get_single("AI Assistant Settings")
	
	# Check if PDF context is enabled
	if not settings.enable_pdf_context:
		print("❌ ERROR: PDF context is not enabled!")
		print("   Enable 'Enable PDF Knowledge Base' in AI Assistant Settings first.")
		return
	
	if not settings.knowledge_pdf:
		print("❌ ERROR: No PDF uploaded!")
		print("   Upload a PDF file in AI Assistant Settings first.")
		return
	
	if not settings.assistant_id:
		print("❌ ERROR: No Assistant ID found!")
		print("   Please re-upload the PDF to create the assistant.")
		return
	
	print(f"\n✓ PDF Context: Enabled")
	print(f"✓ Assistant ID: {settings.assistant_id}")
	print(f"✓ Vector Store ID: {settings.vector_store_id}")
	print(f"✓ PDF File: {settings.knowledge_pdf}")
	
	# Get current settings
	from ai_module.agents.assistants_api import update_assistant_on_openai
	from ai_module.agents.assistant_spec import DEFAULT_INSTRUCTIONS
	
	instructions = (settings.instructions or DEFAULT_INSTRUCTIONS).strip()
	model = settings.model or "gpt-4o-mini"
	assistant_name = getattr(settings, 'assistant_name', None) or "CRM Assistant with Knowledge Base"
	
	print(f"\n📝 Current Settings:")
	print(f"   Model: {model}")
	print(f"   Name: {assistant_name}")
	print(f"   Instructions length: {len(instructions)} characters")
	print(f"   Instructions preview: {instructions[:100]}...")
	
	print("\n🔄 Updating Assistant on OpenAI...")
	
	try:
		updated = update_assistant_on_openai(
			assistant_id=settings.assistant_id,
			instructions=instructions,
			model=model,
			name=assistant_name
		)
		
		if updated:
			print("\n✅ SUCCESS: Assistant updated successfully on OpenAI!")
			print(f"   Assistant ID: {settings.assistant_id}")
			print("\n💡 The AI will now use the updated prompt from OpenAI.")
			print("   Test it by sending a message via WhatsApp or the chat interface.")
		else:
			print("\n❌ ERROR: Failed to update assistant!")
			print("   The assistant may have been deleted on OpenAI.")
			print("   Please re-upload the PDF in AI Assistant Settings to recreate it.")
			
	except Exception as e:
		print(f"\n❌ ERROR: {str(e)}")
		import traceback
		traceback.print_exc()
	
	print("\n" + "=" * 60)


if __name__ == "__main__":
	frappe.init(site="your-site-name")
	frappe.connect()
	force_update_assistant()
	frappe.db.commit()
	frappe.destroy()

