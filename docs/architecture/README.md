# Architecture

How the Historical Atlas is built — runtime surfaces, the frontend foundation, and the pipeline.
For *how to run* things, see [../implementation-docs/](../implementation-docs/).

- [system-overview.md](system-overview.md) — whole-system: runtime surfaces, routing, repository responsibilities, the three pipeline tracks.
- [frontend-app.md](frontend-app.md) — the public `web/` Atlas SPA: three-layer state, hook seam, re-render budget, scope/viewport model.
- [data-pipeline.md](data-pipeline.md) — all pipeline tracks (Wikidata, OHM, agent) and the Laravel import layer.
- [admin-map-editor.md](admin-map-editor.md) — the admin (Inertia) entity editor and map UI, as built.
- [ohm-integration.md](ohm-integration.md) — OpenHistoricalMap tile / MapLibre integration reference.
- [tags.md](tags.md) — the faceted tag vocabulary for chronicles and entities: storage, derivation, `tags:sync`, API filters, UI.
- [entity-images.md](entity-images.md) — entity images linked (not copied) from Wikimedia Commons with author/license: `entity:fetch-images`, the admin Images panel, SPA display.
