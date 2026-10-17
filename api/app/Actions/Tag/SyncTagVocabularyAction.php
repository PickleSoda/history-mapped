<?php

declare(strict_types=1);

namespace App\Actions\Tag;

use App\Enums\TagFacet;
use App\Models\Tag;
use Illuminate\Support\Facades\DB;

/**
 * Upsert the controlled vocabulary (database/data/tags/vocabulary.json).
 *
 * The file is the source of truth for every facet except Topic: tags missing
 * from it are deleted (their pivot rows cascade). Topic tags are left alone.
 */
class SyncTagVocabularyAction
{
    public const PATH = 'data/tags/vocabulary.json';

    /**
     * @param  array{facets: array<string, list<array<string, mixed>>>}|null  $vocabulary  defaults to the file at PATH
     * @return array{upserted: int, deleted: int}
     */
    public function __invoke(?array $vocabulary = null): array
    {
        $vocabulary ??= json_decode((string) file_get_contents(database_path(self::PATH)), true, flags: JSON_THROW_ON_ERROR);

        $now = now();
        $rows = [];
        foreach ($vocabulary['facets'] as $facet => $tags) {
            $facet = TagFacet::from($facet);
            foreach (array_values($tags) as $i => $tag) {
                $rows[] = [
                    'slug' => $tag['slug'],
                    'name' => $tag['name'],
                    'facet' => $facet->value,
                    'parent_slug' => $tag['parent'] ?? null,
                    'description' => $tag['description'] ?? null,
                    'start_year' => $tag['start_year'] ?? null,
                    'end_year' => $tag['end_year'] ?? null,
                    'sort_order' => $i,
                    'created_at' => $now,
                    'updated_at' => $now,
                ];
            }
        }

        return DB::transaction(function () use ($rows): array {
            // Parents first, so the self-referencing FK holds row by row.
            Tag::query()->upsert(
                array_map(fn (array $r): array => ['parent_slug' => null] + $r, $rows),
                ['slug'],
                ['name', 'facet', 'description', 'start_year', 'end_year', 'sort_order', 'updated_at'],
            );
            foreach ($rows as $r) {
                Tag::query()->where('slug', $r['slug'])->update(['parent_slug' => $r['parent_slug']]);
            }

            $deleted = Tag::query()
                ->where('facet', '!=', TagFacet::Topic->value)
                ->whereNotIn('slug', array_column($rows, 'slug'))
                ->delete();

            return ['upserted' => count($rows), 'deleted' => $deleted];
        });
    }
}
