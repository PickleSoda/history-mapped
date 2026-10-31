## Editing fields

`get_entity_context` returns `fields` — every field `update_entity_fields` can change, with its current value (null = not set yet) — and `attribute_fields` — the fields specific to this entity's type, each with its kind and, for a choice, the allowed `values`. All of them are editable:

- **Plain fields** (summary, significance, dates, date_method, impact_score, confidence, icon_class, …): pass them to `update_entity_fields` by name. Send only what changes.
- **Type-specific fields**: `attributes: {"key": value}`, using a choice's allowed values exactly as listed.
- **Tags and alternative names**: `add_tags` / `remove_tags`, `add_alternative_names` / `remove_alternative_names`. Never resend the whole list.
- **To empty a field**: `clear: ["field"]` (an attribute key works too).
- **The map point**: `set_entity_location`, never a field update.

Fill in empty fields only when the operator or a source supports the value. If a tool returns an `error`, it says what to send instead: fix that one thing and retry once.
