<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Services\WikimediaImages;
use Illuminate\Database\Query\Builder;
use Illuminate\Support\Facades\DB;

/**
 * Finds images for entities with a Wikidata id and stores them as links in
 * `attributes.media_refs`. Nothing is copied: each item points at the Commons
 * thumbnail and carries the author/license to credit.
 *
 * Per entity, best first, at most MAX_ITEMS:
 *  1. Wikidata P18 (image).
 *  2. Without P18, the English Wikipedia lead image, if it is a Commons file.
 *     States, dynasties and units take it last: their Wikidata map, flag and
 *     arms are curated, while the article's lead image is often incidental.
 *  3. The other image properties for the entity type (flag, coat of arms, map…).
 *
 * An entity with nothing found gets `media_refs = []`, so later runs skip it
 * unless refreshed. Entities an admin has curated (`_media_curated_at`) are
 * never selected by the command.
 */
class FetchEntityImagesAction
{
    public const MAX_ITEMS = 4;

    /** Attribute an admin save sets; the fetcher leaves those entities alone. */
    public const CURATED_KEY = '_media_curated_at';

    /** Properties tried, best first. Types not listed use DEFAULT_ORDER. */
    private const ORDER = [
        'political_entity' => ['P18', 'P242', 'P41', 'P94', 'P1621', 'P158'],
        'dynasty' => ['P18', 'P94', 'P41'],
        'city' => ['P18', 'P94', 'P41', 'P242', 'P1621'],
        'military_unit' => ['P18', 'P94', 'P41', 'P154'],
        'educational_institution' => ['P18', 'P154', 'P158', 'P94'],
        'religious_movement' => ['P18', 'P154', 'P41'],
        'infrastructure_monument' => ['P18', 'P3311', 'P242', 'P1621'],
        'trade_route' => ['P18', 'P15', 'P242'],
        'language' => ['P18', 'P1846'],
        'archaeological_culture' => ['P18', 'P1846', 'P242'],
        'migration' => ['P18', 'P1846', 'P242'],
        'person' => ['P18', 'P94'],
    ];

    private const DEFAULT_ORDER = ['P18', 'P242', 'P1621', 'P94', 'P41', 'P154'];

    /** Types whose Wikipedia lead image goes after their Wikidata images. */
    private const LEAD_LAST = ['political_entity', 'dynasty', 'military_unit'];

    public function __construct(private readonly WikimediaImages $wikimedia) {}

    /**
     * Entities the fetcher may fill: a Wikidata id, not curated by an admin
     * and, unless refreshing, not checked yet.
     */
    public static function pending(bool $refresh = false): Builder
    {
        return DB::table('entities')
            ->whereNotNull('wikidata_id')
            ->whereRaw('attributes -> ? IS NULL', [self::CURATED_KEY])
            ->when(! $refresh, fn (Builder $q) => $q->whereRaw("attributes -> 'media_refs' IS NULL"));
    }

    /**
     * Images for up to WikimediaImages::BATCH entities.
     *
     * @param  iterable<object{entity_id: string, wikidata_id: string, entity_type: string}>  $entities
     * @return array<string, list<array<string, mixed>>> entity_id => items, primary first ([] = none found)
     */
    public function find(iterable $entities): array
    {
        $byQid = [];
        foreach ($entities as $entity) {
            $qid = strtoupper(trim((string) $entity->wikidata_id));
            if (preg_match('/^Q\d+$/', $qid)) {
                $byQid[$qid][] = $entity;
            }
        }

        $claims = $this->wikimedia->wikidataFiles(array_keys($byQid));

        // Wikipedia lead images, only for items without a P18.
        $titles = [];
        foreach ($claims as $qid => $c) {
            if (! isset($c['files']['P18']) && $c['wikipedia'] !== null) {
                $titles[$qid] = $c['wikipedia'];
            }
        }
        $leads = $titles === [] ? [] : $this->wikimedia->wikipediaPageImages(array_values($titles));

        /** @var array<string, list<array{file: string, kind: string, source: string, property: ?string}>> $picks */
        $picks = [];
        foreach ($byQid as $qid => $rows) {
            foreach ($rows as $entity) {
                $picks[$entity->entity_id] = $this->candidates(
                    $entity->entity_type,
                    $claims[$qid]['files'] ?? [],
                    isset($titles[$qid]) ? ($leads[$titles[$qid]] ?? null) : null,
                );
            }
        }

        $files = array_values(array_unique(array_merge(...array_map(
            fn (array $p): array => array_column($p, 'file'),
            array_values($picks) ?: [[]],
        ))));
        $info = $files === [] ? [] : $this->wikimedia->fileInfo($files);

        $out = [];
        foreach ($picks as $entityId => $candidates) {
            $items = [];
            foreach ($candidates as $c) {
                if (isset($info[$c['file']]) && count($items) < self::MAX_ITEMS) {
                    $items[] = WikimediaImages::item($info[$c['file']], $c['kind'], $c['source'], $c['property']);
                }
            }
            $out[$entityId] = $items;
        }

        return $out;
    }

    /**
     * Write `media_refs` for many entities in one statement.
     *
     * @param  array<string, list<array<string, mixed>>>  $media  entity_id => items
     */
    public function save(array $media): int
    {
        if ($media === []) {
            return 0;
        }

        $rows = [];
        foreach ($media as $id => $items) {
            $rows[] = ['id' => $id, 'media' => $items];
        }

        return DB::update(<<<'SQL'
            UPDATE entities e
            SET attributes = jsonb_set(CASE WHEN jsonb_typeof(e.attributes) = 'object' THEN e.attributes ELSE '{}'::jsonb END, '{media_refs}', v.media)
            FROM jsonb_to_recordset(?::jsonb) AS v(id uuid, media jsonb)
            WHERE e.entity_id = v.id
            SQL, [json_encode($rows, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)]);
    }

    /**
     * Files to try for one entity, in display order, one per property.
     *
     * @param  array<string, list<string>>  $files  property => file names
     * @return list<array{file: string, kind: string, source: string, property: ?string}>
     */
    private function candidates(string $type, array $files, ?string $lead): array
    {
        $out = [];
        foreach (self::ORDER[$type] ?? self::DEFAULT_ORDER as $property) {
            foreach ($files[$property] ?? [] as $file) {
                if ($file !== $lead && ! in_array($file, array_column($out, 'file'), true)) {
                    $out[] = ['file' => $file, 'kind' => WikimediaImages::PROPERTIES[$property], 'source' => 'wikidata', 'property' => $property];

                    break;
                }
            }
        }

        if ($lead !== null) {
            // The article's lead image is often the item's flag or map: say so.
            $property = null;
            foreach ($files as $p => $names) {
                if (in_array($lead, $names, true)) {
                    $property = $p;

                    break;
                }
            }
            $entry = ['file' => $lead, 'kind' => WikimediaImages::PROPERTIES[$property] ?? 'image', 'source' => 'wikipedia', 'property' => $property];
            in_array($type, self::LEAD_LAST, true) ? $out[] = $entry : array_unshift($out, $entry);
        }

        return $out;
    }
}
