# Entity images

Entities show freely licensed pictures from Wikimedia Commons. **Nothing is
copied or hosted**: we store links to the Commons thumbnails, and the
author/license data their reuse terms ask us to display. The browser loads each
image straight from Wikimedia.

## Storage

The images live in `entities.attributes.media_refs`, an ordered list where the
first entry is the primary image. The API returns it as `media_refs`.

```json
{
  "type": "image",
  "kind": "image | flag | coat_of_arms | seal | logo | map | plan",
  "url": "https://thumb.wikimedia.org/…/960px-File.jpg",
  "original_url": "https://upload.wikimedia.org/…/File.jpg",
  "page_url": "https://commons.wikimedia.org/wiki/File:File.jpg",
  "file": "File.jpg",
  "caption": "…",
  "author": "…",
  "license": "CC BY-SA 4.0",
  "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
  "attribution_required": true,
  "width": 960, "height": 720,
  "source": "wikidata | wikipedia | commons | external",
  "property": "P18",
  "fetched_at": "2026-10-18T…"
}
```

- `media_refs: []` means "checked, nothing found". A missing key means the
  entity has not been checked yet.
- `attributes._media_curated_at` is set when an admin saves images. The fetcher
  never touches those entities again.
- Entity writes that leave these two keys out keep them, so an admin form save
  or a pipeline `--force` re-import does not drop linked images
  (`UpdateEntityAction::PRESERVED_ATTRIBUTES`).

## Fetching (`entity:fetch-images`)

```bash
php artisan entity:fetch-images            # entities with a QID not checked yet, highest impact first
php artisan entity:fetch-images --refresh  # re-check everything except admin-curated entities
php artisan entity:fetch-images --type=person --limit=500 --dry-run
php artisan entity:fetch-images --report   # coverage by type; no fetching
```

The command works in batches of 50 (`FetchEntityImagesAction`, `App\Services\WikimediaImages`):

1. **Wikidata Query Service**: each item's best-rank image claims (P18 image,
   P41 flag, P94 coat of arms, P158 seal, P154 logo, P242/P1621/P15/P1846/P1943
   maps, P3311 plan) and its English Wikipedia title.
2. **English Wikipedia `pageimages`**: only for items without P18. The lead
   image is used only if it is a Commons file; local enwiki files are usually
   non-free. For states, dynasties and military units it goes after their
   Wikidata map, flag and arms.
3. **Commons `imageinfo`**: a 960px thumbnail (a standard Wikimedia step),
   size and license metadata. Missing, non-image and `NonFree` files are
   skipped.

Each entity gets at most 4 images, one per property, in a per-type order
(`FetchEntityImagesAction::ORDER`). Entities **without** a Wikidata id are not
matched by name, because the namesake risk is too high; pick their images in
the admin. A batch that fails is not written, so the next run retries it.

Run the command after a campaign ingest so new entities get images. Images
reach production with the content dump (they are part of `entities`).

## Admin: choosing an image

The entity editor has an **Images** panel (`components/entity-images-panel.tsx`,
`Admin\EntityImageController`). The admin entity list has an **Image** filter
(Has image / No image) for finding entities still without one.

- Shows the linked images with their credits. You can reorder them (the first
  is primary), change their kind, edit the caption, or remove one.
- **Find an image** offers four sources:
  - **Wikidata**: every image claim of the entity's item, or of a QID you type.
  - **Wikipedia**: lead images of matching English Wikipedia articles.
  - **Commons**: a file search.
  - **Paste URL**: a Commons/Wikipedia file page or `upload.wikimedia.org`
    link is resolved to its Commons file. Any other https image is allowed
    if you type its author and license (license is required).
- On save, the license of each Commons file is re-read from Commons; the
  client's copy is not trusted.

Routes (in the `admin.access` group):

| Route | Purpose |
|-------|---------|
| `GET /entities/{entity}/images` | the stored list |
| `GET /entities/{entity}/images/candidates?source=wikidata\|wikipedia\|commons\|url&q=` | candidates from one source |
| `PUT /entities/{entity}/images` | save (`permission:entities.write`) |

## Display (Atlas SPA)

- **Entity page**: the primary image under the title, with its caption and
  credit line (author · license · Wikimedia Commons, each part linked). The
  other images appear in "Sources & media", each with its own credit.
- **Detail panel**: a thumbnail of the primary image, with its credit.
- Flags, coats of arms, seals and logos are shown whole and small; photos and
  maps are larger. An image that fails to load is hidden.
- Helpers: `web/src/lib/entity-format.ts` (`mediaItems`, `primaryImage`,
  `isEmblem`, `mediaHost`), `web/src/components/atlas/EntityImage.tsx`.
