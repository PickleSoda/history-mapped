<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Enums\ConfidenceLevel;
use App\Models\Entity;
use App\Models\GeometrySnapshot;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * @extends Factory<GeometrySnapshot>
 *
 * NOTE: The geometry_snapshots table has a CHECK constraint requiring at least
 * one geometry column (geom or territory_geom) to be non-null. Because
 * PostgreSQL CHECK constraints cannot be deferred, Eloquent's regular
 * create() will fail. This factory bypasses Eloquent by issuing a raw INSERT
 * that includes a real PostGIS geometry so the constraint is always satisfied.
 */
class GeometrySnapshotFactory extends Factory
{
    protected $model = GeometrySnapshot::class;

    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        $yearStart = fake()->numberBetween(-500, 1800);
        $yearEnd = $yearStart + fake()->numberBetween(0, 200);

        return [
            'snapshot_id' => Str::uuid()->toString(),
            'entity_id' => Entity::factory(),
            'year_start' => $yearStart,
            'year_end' => $yearEnd,
            'label' => fake()->optional()->sentence(4),
            'confidence' => fake()->randomElement(ConfidenceLevel::cases())->value,
            'notes' => fake()->optional()->paragraph(1),
            'display_priority' => fake()->numberBetween(0, 10),
            'created_by' => 'factory',
            // Default geometry included so CHECK constraint is always satisfied
            '_geojson' => json_encode(['type' => 'Point', 'coordinates' => [0.0, 0.0]]),
        ];
    }

    /**
     * Attach to an existing entity.
     */
    public function forEntity(Entity $entity): static
    {
        return $this->state(fn () => [
            'entity_id' => $entity->entity_id,
        ]);
    }

    /**
     * Set a specific year range.
     */
    public function forYears(int $start, int $end): static
    {
        return $this->state(fn () => [
            'year_start' => $start,
            'year_end' => $end,
        ]);
    }

    /**
     * Set an explicit point/line GeoJSON geometry.
     *
     * @param  array<string, mixed>  $geojson
     */
    public function withPointGeometry(array $geojson): static
    {
        return $this->state(fn () => [
            '_geojson' => json_encode($geojson),
            '_territory_geojson' => null,
        ]);
    }

    /**
     * Set an explicit polygon/multipolygon territory geometry.
     *
     * @param  array<string, mixed>|null  $geojson
     */
    public function withTerritoryGeometry(?array $geojson = null): static
    {
        $territory = $geojson ?? [
            'type' => 'Polygon',
            'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
        ];

        return $this->state(fn () => [
            '_geojson' => null,
            '_territory_geojson' => json_encode($territory),
        ]);
    }

    /**
     * Override createOne() to use a raw INSERT that satisfies the gs_has_geometry
     * CHECK constraint by writing the geometry column in the same statement.
     *
     * @param  array<string, mixed>  $attributes
     */
    public function createOne($attributes = []): GeometrySnapshot
    {
        $raw = $this->state($attributes)->raw();

        // Resolve entity factory if needed
        if ($raw['entity_id'] instanceof Factory) {
            /** @var Entity $entityModel */
            $entityModel = $raw['entity_id']->create()->first();
            $raw['entity_id'] = $entityModel->entity_id;
        } elseif ($raw['entity_id'] instanceof Model) {
            $raw['entity_id'] = $raw['entity_id']->entity_id;
        }

        $geojson = $raw['_geojson'] ?? json_encode(['type' => 'Point', 'coordinates' => [0.0, 0.0]]);
        $territoryGeojson = $raw['_territory_geojson'] ?? null;
        unset($raw['_geojson']);
        unset($raw['_territory_geojson']);

        $now = now();
        $snapshotId = $raw['snapshot_id'] ?? Str::uuid()->toString();

        $geomExpr = $geojson !== null ? 'ST_GeomFromGeoJSON(?)' : 'NULL';
        $territoryExpr = $territoryGeojson !== null ? 'ST_GeomFromGeoJSON(?)' : 'NULL';

        $sql = <<<SQL
            INSERT INTO geometry_snapshots
                (snapshot_id, entity_id, year_start, year_end,
                 geom, territory_geom,
                 label, confidence, notes, display_priority,
                 created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, {$geomExpr}, {$territoryExpr}, ?, ?::confidence_level, ?, ?, ?, ?, ?)
            SQL;

        $bindings = [
            $snapshotId,
            $raw['entity_id'],
            $raw['year_start'],
            $raw['year_end'],
        ];

        if ($geojson !== null) {
            $bindings[] = $geojson;
        }

        if ($territoryGeojson !== null) {
            $bindings[] = $territoryGeojson;
        }

        $bindings = array_merge($bindings, [
            $raw['label'] ?? null,
            $raw['confidence'] ?? null,
            $raw['notes'] ?? null,
            $raw['display_priority'] ?? 0,
            $raw['created_by'] ?? 'factory',
            $now,
            $now,
        ]);

        DB::statement($sql, $bindings);

        return GeometrySnapshot::findOrFail($snapshotId);
    }

    /**
     * Override create() to route through createOne().
     *
     * @param  array<string, mixed>  $attributes
     * @return Collection<int, GeometrySnapshot>|GeometrySnapshot
     */
    public function create($attributes = [], ?Model $parent = null): Collection|GeometrySnapshot
    {
        if ($this->count === null) {
            return $this->createOne($attributes);
        }

        $models = new Collection;
        for ($i = 0; $i < $this->count; $i++) {
            $models->push($this->createOne($attributes));
        }

        return $models;
    }
}
