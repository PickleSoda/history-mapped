# Topic Ref-Table Record Schema

> Schema for records written to `topic_<slug>_ref.jsonl` by the topic pipeline.

## Purpose

The topic scraper may discover non-entity records intended for reference tables. These records are written separately and tagged with `_ref_type`.

## Schema

```jsonc
{
  "qid": "Q12345",
  "label": "Some Reference Item",
  "description": "Optional description",
  "aliases": ["Alias A", "Alias B"],

  // Arbitrary source payload carried from scraper
  "properties": {},

  // Required routing key for Laravel import/ref handlers
  "_ref_type": "civilization_ref"
}
```

## Required Field

- `_ref_type`: identifies which reference table pipeline/import logic should route to.

## Known Behavior

- Topic command separates typed entities, ref items, and untyped items.
- Ref items are not merged into the main entity JSONL output.
- The `_ref_type` key is injected at write time in the topic command.

## Compatibility Notes

- Ref-table records are intentionally flexible because categories evolve.
- Keep top-level keys stable and avoid deeply nested polymorphic payloads when possible.
