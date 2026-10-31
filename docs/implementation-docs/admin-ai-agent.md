# Admin AI Agent — Operator Guide

The **Admin AI Agent** is a route-bound AI editing assistant embedded in the Laravel/Inertia admin. It lets authorised editors describe changes to an entity or chronicle in natural language; the agent proposes discrete, reviewable edits which are staged for human confirmation before touching the database.

---

## 1. Feature overview

- **Contextual chat** — every conversation is pinned to a specific entity or chronicle (`context_type` + `context_id`).
- **Propose → preview → confirm** flow — the agent never writes directly to the database. All writes go through `agent_proposed_changes` / `agent_proposed_change_parts` (status: `pending`). The operator reviews a human-readable diff in the UI and clicks **Apply** or **Discard** per part.
- **Partial apply** — each change is a set of independently applicable _parts_ (e.g. "create entity", "set location"). Parts may have dependency order (`depends_on`); the UI enforces it.
- **Audit trail** — every applied change records `applied_at`, the applying user, and sets `created_by = 'agent:{user_id}'` on created entities.

---

## 2. Propose → preview → confirm in detail

```
POST /ai/chat  {context_type, context_id, prompt|messages}
               └─ streams SSE text (ai-sdk/react DefaultChatTransport)

   Agent generates tool calls
   └─ each staging tool calls buildParts() → inserts agent_proposed_change_parts (status=pending)

   UI displays diff per part
   ├─ POST /ai/proposals/{change}/parts/{key}/apply   → ProposalApplier::apply()
   └─ POST /ai/proposals/{change}/parts/{key}/discard → marks status=discarded
```

The apply endpoint:
1. Resolves `depends_on` chains so nested creates (e.g. create entity then set location) receive the newly assigned UUID.
2. Calls the tool's `applyPart(payload, resolved)`.
3. Sets `status = applied`, `applied_at = now()`, `result_id = <created id>`.

---

## 3. Tool list

| Tool | Type | Description |
|---|---|---|
| `get_entity_context` | read-only | Live state: every field `update_entity_fields` can change (`fields`), the type's attributes with allowed values and current values (`attribute_fields`, from `App\Support\EntityAttributeCatalog`), location, dates, relationships. |
| `verify_wikidata` | read-only | Looks up a QID and returns label + P31 + coordinates. |
| `find_place` | read-only | Name → candidate points: our entities (name / alias / trigram), then OHM Nominatim. Flags `approximate` points — generic centroids shared by 5+ records. |
| `point_from_offset` | read-only | Anchor + distance (km, mi, nmi, roman_mile) + compass direction → great-circle destination point. |
| `point_between` | read-only | Two anchors + fraction (0.5 = midpoint) → great-circle intermediate point. |
| `nearest_coast` | read-only | Anchor → nearest point on an OSM coastline (live Overpass query; `OVERPASS_BASE_URL`), optionally `offset_km` inland (+) or out to sea (−). Modern coastline. |
| `create_entity` | staging (primary) | Proposes a new entity record with type, dates, location. |
| `set_entity_location` | staging | Proposes the primary point (+ optional `location_name`, `location_confidence`); keeps the territory polygon. |
| `update_entity_fields` | staging | Proposes changes to anything the admin edit form edits — scalar fields (incl. the long-form `description`), date resolution, confidence, display, verification status (apply needs `entities.verify`), tags / alternative names (add/remove), type-specific attributes (catalog-checked), and `clear` to empty fields. Validated with `UpdateEntityRequest`'s rules; applied by `ApplyEntityEditsAction` (the form's write path, seeded from the entity so nothing unsent is lost). |
| `set_entity_wikidata` | staging | Proposes setting/updating the Wikidata QID and cascading to source citations + geo refs. |
| `create_relationship` | staging | Proposes a typed relationship; optionally creates the target entity as a nested part. |
| `merge_duplicate_entities` | staging | Proposes merging a duplicate into a survivor entity (calls `MergeEntityAction`). |

The **EntityEditorAgent** has all 12 entity tools. The **ChronicleEditorAgent** has 13 (no `get_entity_context`; adds the chronicle-entry tools); the **GlobalAgent** has all 15; the **EntityCreatorAgent** has `create_entity`, `verify_wikidata` and the four place tools. The place tools are read-only lookups: they compute a point and the model passes it to `set_entity_location` / `create_entity`. The prompts share two sections — `resources/views/ai/instructions/partials/fields.blade.php` (what is editable and how) and `placement.blade.php` (phrase → anchor + one operation → point, with unit conversions).

A tool argument the model can fix is rejected with a `ToolArgumentException`, whose message is returned to the model as the tool result (other failures stay generic).

### Namesake guard (Wikidata)

`set_entity_wikidata` refuses a QID whose P31 marks a namesake (a song, street, film… — `SetEntityWikidata::BOGUS_P31`) and refuses to stage the change. This prevents accidentally tagging, say, an empire with a ship named after it.

---

## 4. Provenance

- **Created entities** have `created_by = 'agent:{user_id}'` on the `entities` table row, where `{user_id}` is the authenticated operator's id.
- **Proposals audit** — `agent_proposed_changes` records `user_id` (who initiated the conversation) and `conversation_id`. `agent_proposed_change_parts` records the `tool`, `payload`, `human_diff`, and timestamps for every staged and applied part. This table is the undo/audit log.

---

## 5. Configuration

### OpenRouter + model

The agent uses the `openrouter` provider configured in `config/ai.php`. Default model:

```
anthropic/claude-haiku-4.5
```

Override via `.env`:

```env
OPENROUTER_API_KEY=sk-or-...
AI_DEFAULT_MODEL=anthropic/claude-haiku-4.5
```

A soft monthly cap of approximately **$20 USD** is recommended for self-hosted deployments. Monitor spend at [openrouter.ai/activity](https://openrouter.ai/activity).

### Conversations table name

Controlled by `config('ai.conversations.tables.conversations', 'agent_conversations')`. If `laravel/ai` changes its default, update `.env` or `config/ai.php` accordingly.

---

## 6. Endpoints & authorisation

| Method | Path | Auth | Gate |
|---|---|---|---|
| `POST` | `/ai/chat` | required | `entities.write` |
| `POST` | `/ai/proposals/{change}/parts/{key}/apply` | required | `entities.write` (must own the change) |
| `POST` | `/ai/proposals/{change}/parts/{key}/discard` | required | owner only (no `entities.write` required) |

Users without `entities.write` receive `403 Forbidden` on the chat and apply endpoints. Discard is intentionally open to the change owner so users can clean up their own staged proposals without write permission.

---

## 7. Retention — `ai:prune-proposals`

The command `php artisan ai:prune-proposals` enforces these rules:

| Data | Retention | Column checked |
|---|---|---|
| `pending` / `discarded` parts | 7 days | `agent_proposed_change_parts.created_at` |
| `applied` parts (audit window) | 1 year | `agent_proposed_change_parts.applied_at` |
| Orphaned parent changes (no parts) | deleted immediately on next prune run | — |
| Chat conversations | 90 days | `agent_conversations.updated_at` |

The command is **scheduled daily** in `routes/console.php`:

```php
Schedule::command('ai:prune-proposals')->daily();
```

The scheduler container (`docker/docker-compose.yml` service `scheduler`) runs `php artisan schedule:run` every minute, so no additional setup is needed.

**Dry-run mode** — inspect what would be deleted without modifying data:

```bash
php artisan ai:prune-proposals --dry-run
```

---

## 8. Running in the container

All Artisan commands run inside the `app` container:

```bash
docker compose -f docker/docker-compose.yml exec app php artisan ai:prune-proposals --dry-run
docker compose -f docker/docker-compose.yml exec app php artisan ai:prune-proposals
```

---

## 9. Choosing the model — `pipeline/eval_admin_agent_models.py`

The agent needs a model that is good at **both** tool-calling _and_ writing summaries from source text, at interactive latency and low cost. `pipeline/eval_admin_agent_models.py` is a standalone (stdlib-only) harness that replays the **real** agent loop against several OpenRouter models and auto-grades the result.

It feeds each model the real system prompt + tool schemas, executes its tool calls with stubs (with **live** Wikidata for `verify_wikidata`), and loops until the model stops — exactly what `EntityEditorAgent` / `ChronicleEditorAgent` do in production.

### Scenarios

| Key | Agent | Probes |
| --- | --- | --- |
| `fix-karnak` | entity editor | verify→set QID, fix location (NL-coord trap), write a summary from source, signed-BCE years |
| `link-new-entity` | entity editor | nested `create_relationship` via `new_target` (must not fabricate a UUID or split into `create_entity`) |
| `chronicle-relate` | chronicle editor | link two of the chronicle's referenced entities by their real ids, write a missing summary (uses the chronicle toolset — no `get_entity_context`) |

### Running it

```bash
python3 pipeline/eval_admin_agent_models.py                      # all scenarios × default models
python3 pipeline/eval_admin_agent_models.py --scenarios chronicle-relate
python3 pipeline/eval_admin_agent_models.py --models openai/gpt-5-mini,mistralai/mistral-medium-3.1
python3 pipeline/eval_admin_agent_models.py --repeat 3           # run each combo N times for variance
```

Key resolution: `--key` → `$OPENROUTER_API_KEY` → `api/.env` → `pipeline/.env`. Per-model output shows the tool-call sequence, an auto-score against the rubric, the proposed summary (for human writing-judgment), and latency/cost/tokens; an aggregate matrix prints at the end.

### Findings (2026-06-24)

All four candidates (`openai/gpt-5-mini`, `mistralai/mistral-medium-3.1`, `google/gemini-3.1-flash-lite`, `qwen/qwen3.7-plus`) passed every rubric check. The differentiators the rubric does **not** score:

- **Argument hygiene** — `gpt-5-mini` (and, less often, `qwen`) over-fill tool args with empty strings / all-zero objects (e.g. `update_entity_fields` with `name:"", entity_type:"", start_year:0`), which our tools would treat as destructive writes. **Mistral** and **Gemini** send only the fields they change.
- **Writing** — `gpt-5-mini`/`qwen` are richest; **Mistral** is very close and keeps the specifics (named pharaohs, architectural nouns); **Gemini** flattens detail.
- **Latency / cost** — Mistral ~5.7 s / ~$0.005; Gemini ~7 s; gpt-5-mini ~30 s and ~3× the cost; qwen slow.

**Chosen: `mistralai/mistral-medium-3.1`** — the only candidate that is simultaneously clean on tool args, near-best on writing, fastest, and cheap.
