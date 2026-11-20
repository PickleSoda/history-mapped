# Demo data set

`load.sh` (run as `pnpm demo:load`) downloads `history-mapped-demo.sql.gz` from the repository's
GitHub release `demo-data-v1` and loads it into the local stack. User guide:
[Local setup § Demo data](../../docs/implementation-docs/setup.md#demo-data). Licence: [LICENSE.md](LICENSE.md).

## What is in the file

A data-only `pg_dump` of the content tables (entities and their aliases, names, locations, dates,
geo refs, tags and timeline entries; relationships; geometry periods; chronicles and their entries;
map stories; sources; tags; the `ref_*` tables). No users, contributions, chats or pipeline hints.

The entities are the ones that did not come from a bulk Wikidata slice (no `attributes._bulk`), plus
any bulk row a chronicle or map story uses: 36,267 entities, 75,201 relationships, 314 chronicles
and 37 map stories in `demo-data-v1`.

## Making a new release of the file

1. Copy the database: `pg_dump -Fc history-mapped | pg_restore -d history-mapped_demo` (create the
   target first; leave out `pipeline_relationship_hints`, `cache`, `sessions`, `jobs` with
   `--exclude-table-data`).
2. In the copy, delete entities where `attributes ? '_bulk'` and no `chronicle_entry_entities` or
   `map_stories` row uses them (the cascade takes about ten minutes); set `entities.reviewer_id` and
   `map_stories.edited_by` to null.
3. Dump: `pg_dump --data-only --no-owner --no-privileges --disable-triggers` with one `-t public.<table>`
   per table listed above (`'ref_*'` for the reference tables), piped through `gzip -9`.
4. Test it: `DEMO_DB=<a freshly migrated database> bash scripts/demo/load.sh --yes <file>`.
5. Attach the file and its `sha256sum` output (`<file>.sha256`) to a new release tag, and change
   the default `VERSION` in `load.sh`. The loader takes either the whole file or parts made with
   `split -b 9500k -d <file> <file>.part-` (`demo-data-v1` is in six parts, because it was uploaded
   through a tool with a 10 MB limit per file).
