<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\MapStory;
use App\Support\MapStory\MapStoryFile;
use App\Support\MapStory\MapStoryVocabulary as V;
use Illuminate\Support\Str;
use stdClass;

/**
 * Start a map story for an entity or a chronicle: a schema-3 skeleton that
 * passes the checks — the attachment, title, kind and year, placeholder intro
 * and outcome, a Wikidata source when the entity has a Q-id, the given sides
 * and units (a battle gets two sides and one body each by default), and one
 * step that places every unit at the entity's map point. Saved through
 * SaveMapStoryAction, so it gets its first revision.
 */
class CreateMapStoryAction
{
    public const PLACEHOLDER = 'To be written.';

    private const SIDE_COLORS = ['#b91c1c', '#1d4ed8', '#047857', '#7c3aed', '#c2410c', '#0f766e'];

    public function __construct(private SaveMapStoryAction $save) {}

    /**
     * @param  list<array<string, mixed>>|null  $sides  [{id, name, color?, polity?, commanders?}]
     * @param  list<array<string, mixed>>|null  $units  [{id, side?, kind, label, …}]
     * @return array{story: MapStory|null, errors: list<string>, warnings: list<string>}
     */
    public function __invoke(Entity|Chronicle $owner, string $kind, string $title, int $year, ?array $sides = null, ?array $units = null, string $source = 'admin', ?int $userId = null, ?string $slug = null): array
    {
        return ($this->save)(null, $this->skeleton($owner, $kind, $title, $year, $sides, $units, $slug), $source, $userId, 'Created');
    }

    /**
     * @param  list<array<string, mixed>>|null  $sides
     * @param  list<array<string, mixed>>|null  $units
     */
    public function skeleton(Entity|Chronicle $owner, string $kind, string $title, int $year, ?array $sides = null, ?array $units = null, ?string $slug = null): stdClass
    {
        $battle = in_array($kind, V::BATTLE_KINDS, true);
        $military = in_array($kind, V::MILITARY_KINDS, true);

        $sides ??= $battle
            ? [['id' => 'side-a', 'name' => 'Side A'], ['id' => 'side-b', 'name' => 'Side B']]
            : [];
        foreach ($sides as $i => $side) {
            $sides[$i] = ['id' => $side['id'] ?? 'side-'.($i + 1), 'name' => $side['name'] ?? 'Side '.($i + 1), 'color' => $side['color'] ?? self::SIDE_COLORS[$i % count(self::SIDE_COLORS)]]
                + array_diff_key($side, array_flip(['id', 'name', 'color']));
        }
        $units ??= $military
            ? array_map(fn (array $side) => [
                'id' => $side['id'].'-main',
                'side' => $side['id'],
                'kind' => $battle ? 'infantry' : 'army',
                'label' => Str::limit((string) $side['name'], 28, ''),
            ], $sides)
            : [];

        $doc = [
            'schema' => V::SCHEMA_VERSION,
            'slug' => $slug ?? $this->freeSlug($title),
            'kind' => $kind,
        ];
        if ($owner instanceof Entity) {
            $doc['entity'] = $owner->wikidata_id
                ? ['name' => $owner->name, 'wikidata' => $owner->wikidata_id]
                : ['name' => $owner->name, 'entity_id' => $owner->entity_id];
        } else {
            $doc['chronicle'] = ['slug' => $owner->slug];
        }
        $doc += [
            'title' => $title,
            'date_label' => $year < 0 ? abs($year).' BC' : (string) $year,
            'year' => $year,
            'intro' => self::PLACEHOLDER,
            'outcome' => self::PLACEHOLDER,
            'sources' => $owner instanceof Entity && $owner->wikidata_id
                ? [['title' => "{$owner->name} — Wikidata", 'url' => "https://www.wikidata.org/wiki/{$owner->wikidata_id}", 'kind' => 'web']]
                : [['title' => 'Sources to be added']],
            'sides' => $sides,
            'units' => $units,
            'features' => [],
        ];

        $step = ['id' => 's1', 'title' => $battle ? 'Deployment' : 'Beginning', 'narrative' => self::PLACEHOLDER];
        if (! $battle) {
            $step['date'] = ['year' => $year];
        }
        $at = $owner instanceof Entity ? $this->point($owner) : null;
        $positions = [];
        if ($at !== null) {
            foreach (array_values($units) as $i => $unit) {
                $point = [round($at[0], 5), round($at[1] + ($i - (count($units) - 1) / 2) * ($battle ? 0.006 : 0.6), 5)];
                $positions[$unit['id']] = in_array($unit['kind'] ?? null, V::POINT_UNIT_KINDS, true)
                    ? ['at' => $point]
                    : ['at' => $point, 'facing' => $i % 2 === 0 ? 0 : 180, 'width' => 1000, 'depth' => 80];
            }
        }
        $step['positions'] = $positions;
        $doc['steps'] = [$step];

        return MapStoryFile::normaliseMaps(MapStoryFile::fromArray($doc));
    }

    /** A kebab-case slug from the title that no story uses yet. */
    public function freeSlug(string $title): string
    {
        $base = Str::limit(Str::slug($title), 100, '') ?: 'story';
        $base = strlen($base) < 3 ? "{$base}-story" : $base;
        $slug = $base;
        for ($n = 2; MapStory::query()->where('slug', $slug)->exists(); $n++) {
            $slug = "{$base}-{$n}";
        }

        return $slug;
    }

    /** @return array{0: float, 1: float}|null the entity's primary map point */
    private function point(Entity $entity): ?array
    {
        $geom = $entity->primaryLocation?->geom;
        $coordinates = is_array($geom) && ($geom['type'] ?? null) === 'Point' ? ($geom['coordinates'] ?? null) : null;

        return is_array($coordinates) && is_numeric($coordinates[0] ?? null) && is_numeric($coordinates[1] ?? null)
            ? [(float) $coordinates[0], (float) $coordinates[1]]
            : null;
    }
}
