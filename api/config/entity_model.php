<?php

declare(strict_types=1);

return [
    /*
    |--------------------------------------------------------------------------
    | Entity model v2 write cutover
    |--------------------------------------------------------------------------
    |
    | When enabled, create/update flows stop writing legacy entity temporal
    | and location columns in the entities table.
    |
    */
    'entity_model_v2_write_enabled' => (bool) env('ENTITY_MODEL_V2_WRITE_ENABLED', false),

    /*
    |--------------------------------------------------------------------------
    | Geometry snapshot compatibility reads
    |--------------------------------------------------------------------------
    |
    | Enables legacy geometry-snapshot compatibility routes during migration.
    |
    */
    'geometry_snapshot_compat_read_enabled' => (bool) env('GEOMETRY_SNAPSHOT_COMPAT_READ_ENABLED', true),
];
