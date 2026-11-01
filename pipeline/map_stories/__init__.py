"""Map stories: step-by-step map replays (battles, campaigns, epidemics, trade
networks, a chronicle's map layer) attached to an entity or a chronicle.

Authoring guide: docs/implementation-docs/map-story-authoring.md. A story is
built by a small Python script in `pipeline/map_stories/stories/` (using the
helpers in `geo.py`), checked with `validate.py`, previewed with `preview.py`,
and written to `api/resources/map-stories/<slug>.json`, which
`php artisan map-stories:sync` loads into the database.
"""
