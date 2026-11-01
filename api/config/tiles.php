<?php

declare(strict_types=1);

/*
|--------------------------------------------------------------------------
| Vector tiles served by the app (TILES_DRIVER=app)
|--------------------------------------------------------------------------
|
| The app can answer the same /tiles/* URLs as the Martin sidecar, from the
| same `tiles.*` PostGIS functions (routes/tiles.php, App\Services\Tiles).
| Contract: docs/schemas/atlas-tiles.md. Which of the two Caddy proxies to is
| the TILES_DRIVER line in docker/.env.prod.
|
*/

return [

    // Public source name => the SQL function Martin would publish under that
    // name: `(z integer, x integer, y integer) RETURNS TABLE (mvt bytea, key text)`,
    // with the TileJSON `vector_layers` in its JSON comment.
    'sources' => [
        'atlas_entities' => [
            'function' => 'tiles.atlas_entities',
            'minzoom' => 0,
            'maxzoom' => 14,
        ],
    ],

    // Seconds a rendered tile stays in the cache store (CACHE_STORE); 0 turns
    // the cache off. Same 5 minutes as Martin's `cache.expiry`, so edits and
    // backfills show up without a restart.
    'cache_ttl' => (int) env('TILES_CACHE_TTL', 300),

    // Cache-Control max-age on tiles and TileJSON (Caddy sets the same on
    // /tiles/* in prod).
    'max_age' => (int) env('TILES_MAX_AGE', 300),

];
