# Reference Docs

Forward-looking design references and proposals — useful for product direction, architecture intent, or
future features, but they **do not describe the live application as-is**. For what exists today, start at
[../README.md](../README.md).

## Contents

- [reference-timeline-schema.md](reference-timeline-schema.md) — proposed `entity_ref_links` table and `/reference/{type}/{id}/timeline` endpoint. **Not implemented** (the live app exposes only the generic `GET /api/v1/reference/{table}`).
- [game-inspired-ui-ux.md](game-inspired-ui-ux.md) — Civilization / Total War visual and interaction inspiration for the intended atlas UX.
- [ohm-cookbook.md](ohm-cookbook.md) — evergreen how-to for extracting OpenHistoricalMap admin boundaries into PostGIS (osmium / ogr2ogr / Overpass techniques).

> The superseded `web_implementation_architecture.md` was replaced by the live
> [../architecture/frontend-app.md](../architecture/frontend-app.md) and moved to
> [../archive/reference/](../archive/reference/).
