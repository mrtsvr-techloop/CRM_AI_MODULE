frappe.ui.form.on('AI Assistant Settings', {
  refresh(frm) {
    const toggle_editability = () => {
      const use = !!frm.doc.use_settings_override;
      const fields = ['assistant_name', 'model', 'project', 'org_id', 'api_key'];
      fields.forEach((f) => frm.set_df_property(f, 'read_only', use ? 0 : 1));
    };

    toggle_editability();

    // Debug Environment
    frm.add_custom_button(__('Debug Environment'), () => {
      frappe.call({
        method: 'ai_module.ai_module.doctype.ai_assistant_settings.ai_assistant_settings.ai_assistant_debug_env',
        type: 'GET',
        callback(r) {
          const data = r.message || {};
          const pretty = JSON.stringify(data, null, 2);
          frappe.msgprint({
            title: __('AI Environment (Effective)'),
            message: `<pre style="white-space:pre-wrap;max-height:60vh;overflow:auto">${frappe.utils.escape_html(pretty)}</pre>`,
            wide: true,
          });
        },
      });
    });

    // Reset Persistence
    frm.add_custom_button(__('Reset Persistence'), () => {
      frappe.confirm(
        __('Delete persisted Assistant ID and phone→thread map?'),
        () => {
          frappe.call({
            method: 'ai_module.ai_module.doctype.ai_assistant_settings.ai_assistant_settings.ai_assistant_reset_persistence',
            args: { clear_threads: 1 },
            callback(r) {
              const info = r.message || {};
              frappe.msgprint(__('Cleared: {0}', [JSON.stringify(info.deleted || {})]));
            },
          });
        }
      );
    });

    // Force Update Assistant
    frm.add_custom_button(__('Force Update Assistant'), () => {
      frappe.call({
        method: 'ai_module.ai_module.doctype.ai_assistant_settings.ai_assistant_settings.ai_assistant_force_update',
        callback(r) {
          const id = r.message;
          frappe.msgprint(__('Assistant updated: {0}', [id || 'OK']));
        },
      });
    });

    // Toggle fields' editability based on override flag
    const toggleEditable = () => {
      const enabled = frm.doc.use_settings_override ? 1 : 0;
      frm.set_df_property('assistant_id', 'read_only', enabled ? 0 : 1);
      frm.set_df_property('instructions', 'read_only', enabled ? 0 : 1);
      toggle_editability();
      frm.refresh_field('assistant_id');
      frm.refresh_field('instructions');
    };
    toggleEditable();
    frm.fields_dict.use_settings_override && frm.fields_dict.use_settings_override.df && frm.fields_dict.use_settings_override.$input && frm.fields_dict.use_settings_override.$input.on('change', toggleEditable);
  },
}); 