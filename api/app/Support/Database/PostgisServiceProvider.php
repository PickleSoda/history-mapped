<?php

declare(strict_types=1);

namespace App\Support\Database;

use Illuminate\Database\Schema\Blueprint;
use Illuminate\Database\Schema\Grammars\PostgresGrammar;
use Illuminate\Support\ServiceProvider;

/**
 * Register Blueprint macros for PostGIS geometry/geography columns.
 *
 * Uses plain 'geometry' and 'geography' types without typmod
 * (no constraints like geometry(Point, 4326)) to avoid clutter
 * from ST_Multi wrappers and ST_SetSRID errors at insert time.
 */
class PostgisServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        // -- Blueprint macros for schema builder
        Blueprint::macro('geometry', function (string $column) {
            /** @var Blueprint $this */
            return $this->addColumn('geometry', $column);
        });

        Blueprint::macro('geography', function (string $column) {
            /** @var Blueprint $this */
            return $this->addColumn('geography', $column);
        });

        // -- Grammar macros so PostgresGrammar knows how to compile the types
        PostgresGrammar::macro('typeGeometry', function (): string {
            return 'geometry';
        });

        PostgresGrammar::macro('typeGeography', function (): string {
            return 'geography';
        });
    }
}
