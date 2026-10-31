# Map stories: admin editor and AI-agent tools — Implementation Plan

> **For agentic workers:** one agent implements this plan, after schema v2 (`2026-10-31-map-story-schema-v2.md`) and generic stories, schema 3 (`specs/2026-10-31-generic-map-stories-design.md`), land. The editor must handle every story kind and attachment, not only battles. Steps use checkbox (`- [ ]`) syntax.

**Goal:** a human in the admin panel and the in-app AI agent can both create, edit, validate and restore battle maps. Neither loses the other's work, and neither loses work written in files.

## Decisions

**Where stories live.** The DB row is the live copy. The files in `api/resources/map-stories/` are seeds and exports.

**New columns on `map_stories`:**
- `edited_at` (timestamp, nullable)
- `edited_by` (users fk, set null on delete, nullable)
- `file_hash` (the hash of the file content last synced from or exported to disk)

**`map-stories:sync`** decides per row:
- **The file is unchanged since the last sync** (`file_hash` matches): skip.
- **The file changed and the row was edited after its last sync:** skip and warn "kept admin edits — export first or use --force".
- **Otherwise:** update.

This is the same idea as `entities:sync-descriptions`.

**`map-stories:export {--slug=*} {--edited}`** writes DB documents to `api/resources/map-stories/<slug>.json` in the builder's exact format: 2-space JSON, key order as stored, a trailing newline. It then updates `file_hash`. A developer can then commit what humans and the AI edited.

**Builder protection.** `pipeline.map_stories build` refuses to overwrite a JSON file that was edited outside the builder, unless it is given `--force`. The builder records the hash of what it last wrote in a committed sidecar, `api/resources/map-stories/.build-hashes.json`. A file whose content no longer matches the sidecar was hand-edited or exported.

**Revisions.** A new `map_story_revisions` table:
- columns: id, map_story_id fk cascade, document jsonb, source (`admin|ai|sync|import|restore`), user_id nullable, note, created_at;
- every save, AI update, sync update and restore writes one revision first;
- keep the newest 50 per story.

**Validation.**
- **Saving** is blocked by `MapStoryDocument::errors()`.
- **Warnings** are shown but don't block. They come from a new `MapStoryWarnings` PHP class that ports the Python validator's main plausibility checks:
  - a unit jumps without an arrow, using the teleport distance per kind;
  - a step spreads too wide;
  - a unit is referenced before it is placed;
  - a land/water mismatch.

  Don't port everything; keep the class small.

**Preview.** There must be one renderer. The admin embeds the public SPA in an iframe at `FRONTEND_URL/?story=<slug>&sstep=<n>&preview=1`.
- **Allowed origins:** in preview mode the SPA listens for `postMessage` only from origins in `VITE_ADMIN_ORIGINS`, a comma-separated list. The dev default is `http://localhost:8000`.
- **Messages from the admin:**
  - `{type:'map-story:document', document}` renders that draft instead of the fetched story;
  - `{type:'map-story:step', index}` jumps to a step;
  - `{type:'map-story:pick', mode:'point'|'path'}` asks for a pick on the map.
- **Messages from the SPA:**
  - `{type:'map-story:ready'}`;
  - `{type:'map-story:picked', at | path}`;
  - `{type:'map-story:unit-dragged', unit, step, at}`, which comes from unit drag in preview mode only;
  - `{type:'map-story:step-changed', index}`.
- **What preview mode turns off:** history pushes, analytics and the entity click-through.
- **Security:** the SPA must parse every document with zod and ignore messages from any origin not on the list.

## Ground rules

- Work in `/home/pickle/code/history-mapped`. Don't commit, and don't run git commands that change state. Wave-1 agents have finished. A peer session is still editing `web/src/components/map/MapCanvas.tsx` in another worktree, so keep changes there to a few lines.
- **PHP and artisan only in Docker:** `docker compose -f docker/docker-compose.yml exec -T app …`. Run Pint with explicit paths.
- **Admin frontend** (`api/resources/js`): run `npm run lint`, `npm run format`, `npm run types:check` and `npm run build` inside the `app` container. Regenerate Wayfinder with `php artisan wayfinder:generate --with-form`; never hand-edit `resources/js/actions|routes`.
- **Web:** use the commands in the schema-v2 plan.
- **Patterns to follow:**
  - Copy the existing admin pages (`resources/js/pages/entities/*`, `pages/ai`) and the AI tools (`app/Ai/Tools/UpdateEntityFields.php`, `ToolRegistry.php`, `ProposalApplier.php`). Match how they handle proposals and approval: if entity edits from the agent go through proposals, map-story edits do too.
  - Put write logic in Action classes (`app/Actions/MapStory/`), not in controllers or tools.

## Tasks

- [ ] **B1. Schema and storage.**
  - Migration for the columns and the revisions table.
  - Models (`MapStoryRevision`).
  - `SaveMapStoryAction`: validate, write a revision, save, set `edited_at`/`by`.
  - `RestoreMapStoryRevisionAction`.
  - Apply the sync policy in `SyncMapStoryFileAction` and write the export command.
  - Builder protection in `pipeline/map_stories/__main__.py`, with a pytest.
  - Feature tests for every sync and export case, revision pruning and restore.
- [ ] **B2. Admin HTTP.** Resource routes under the admin prefix, using the same auth and permission middleware as entity editing:
  - index (filters: kind, edited, search) and show/edit;
  - store (from an entity: a skeleton doc);
  - update (whole document, returning errors and warnings);
  - validate (dry run);
  - revisions (list, show, restore);
  - destroy (hard-delete the row only; say in the UI that the file may re-seed it on the next sync).

  Write feature tests.
- [ ] **B3. Admin UI** (Inertia + React, following the admin's components and styling):
  - **Index page:** a "Battle maps" entry in the sidebar nav.
  - **Edit page:** a split view, with structured editing on the left and the preview iframe on the right, plus a step scrubber synced both ways.
  - **Left tabs:**
    - **Overview:** title, kind, year, date_label, intro, outcome, uncertainty, sources and alt_sites.
    - **Sides and units:** an editable table each.
      - Sides: colours with a swatch, commanders and polities with entity search to fill QIDs and check their names, and contingents.
      - Units: kind select, label, side and contingent, strength and `strength_n`, ranks, commander, QID.
    - **Terrain:** a list, with geometry edited through the existing `map-editor.tsx` (MapLibre + mapbox-gl-draw) in a dialog. Points, lines and areas follow the kind's geometry type.
    - **Steps:**
      - a reorderable list;
      - per step: title, time and narrative (with a character counter against the validator's limits), light, wind, sun, focus and camera ("use current preview view");
      - a positions table, one row per unit with fields shown only when set or on demand, and a "pick on map" button on each `at`;
      - moves and notes with "pick path" or "pick point";
      - beats as nested sub-panels;
      - terrain_state.
    - **JSON:** a raw editor with live validation; on parse errors it blocks the switch back to the form.
  - **Saving:** the Save button shows server errors next to the field when it can map the path, and in a list otherwise. Warnings appear in a collapsible panel.
  - **Revisions:** a drawer with restore.
  - **Entity edit page:** shows its map stories with an "Add battle map" button.
  - **Tests:** add vitest tests where the admin already has page tests.
- [ ] **B4. SPA preview bridge.** A new `web/src/hooks/useStoryPreviewBridge.ts`, plus the minimal hooks in `StoryOverlay` and `useMapStory`, implementing the protocol above. Unit drag in preview mode uses MapLibre's feature drag on the unit layers and emits the new centre on drop.
  - Add `VITE_ADMIN_ORIGINS` to the env examples and the prod env doc. Read the deploy docs and say in your report which variable the user must set on the droplet; don't change prod.
  - Add vitest tests for the origin filter and the message parsing.
- [ ] **B5. AI-agent tools** in `app/Ai/Tools/`, registered like the existing ones:
  - **`get_map_story`** — arguments: `slug` or `entity_id`, plus `part`, one of `overview|sides|units|terrain|steps|step:<id>|full`. Each part is compact, and `full` is capped at about 60k characters, with a "use part=" hint when it is larger. Step ids and array indices appear in the output so patches can address them.
  - **`create_map_story`** — arguments: `entity_id`, `kind`, `title`, `year`, and optional `sides` and `units`. It returns a skeleton through `SaveMapStoryAction`.
  - **`update_map_story`** — arguments: `slug`, `ops` (RFC 6902 JSON Patch: add, replace, remove, move, copy, test) and `note`. The ops apply atomically: validate, then reject the whole patch with the errors, or save with a revision whose source is `ai`. It returns the warnings. Use a maintained JSON-Patch library if one is already installed; otherwise write a small, tested implementation of those six ops.
  - **`validate_map_story`** — arguments: `slug` or an inline `document`. It returns the errors and the warnings.
  - **Geo arguments:** the existing geo tools (`FindPlace`, `PointFromOffset`, `PointBetween`, `NearestCoast`) give coordinates, and the prompt partial says to use them for `at` and `path` values.
  - **Prompt partial:** add one for map stories, in the same place and style as the fields partial. It covers the document shape in about 40 lines, the patching rules, "mark reconstructions `conjectural`", and a link to the authoring guide.
  - **`create_entity`:** also add `description` to it (a known gap).
  - **Tests:** feature tests per tool, covering a happy path, a validation rejection and atomicity.
- [ ] **B6. Docs.** Update:
  - `docs/implementation-docs/map-story-authoring.md`: a section on the editing flows and the sync/export policy;
  - `admin-ai-agent.md`: the new tools;
  - `docs/architecture/admin-map-editor.md`: the story editor and the preview bridge;
  - `content-data-transfer.md`: `map_stories` and `map_story_revisions` in the content tables. Check whether revisions belong in the content dump or should be excluded like per-user data, then decide and say why.
- [ ] **B7. Verify end to end** in the browser with the claude-in-chrome tools, creating your own tabs:
  - edit a step's narrative and one unit's position in the admin (by picking on the map), save, and see it in the SPA;
  - the AI tool path: call `update_map_story` through the admin AI page with a small patch, or through a test if the AI page needs a live key;
  - restore a revision;
  - `map-stories:export` then `map-stories:sync` is a no-op;
  - the builder refuses to overwrite the exported file.

  Revert any demo edits to the sample stories with a restore.
  - Run the full PHP suite, admin lint/format/types/build, and web vitest/tsc/eslint/build.

**Report** in at most 20 lines: routes, tools, tests, the env vars for prod, and any rough edges in the editor.
