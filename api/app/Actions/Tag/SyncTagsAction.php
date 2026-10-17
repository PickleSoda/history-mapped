<?php

declare(strict_types=1);

namespace App\Actions\Tag;

use App\Enums\TagSource;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Support\Facades\DB;

/**
 * Replace a chronicle's or entity's tags from one source.
 *
 * Sources rank Manual > Curated > Derived: writing a source replaces its own
 * rows and every lower-ranked row, and leaves higher-ranked rows alone. A
 * chronicle's Manual save is its whole tag set (the admin edits all of it); an
 * entity's Manual tags sit beside its Derived ones, which `tags:sync` owns.
 * Ancestors are stored too, so filters are plain lookups.
 */
class SyncTagsAction
{
    public function __construct(private readonly ResolveTagsAction $resolve) {}

    /**
     * @param  iterable<mixed>  $tags  slugs or display names
     * @return list<string> the slugs written (with ancestors)
     */
    public function __invoke(Chronicle|Entity $model, iterable $tags, TagSource $source = TagSource::Manual): array
    {
        [$table, $key] = $model instanceof Chronicle
            ? ['chronicle_tags', 'chronicle_id']
            : ['entity_tags', 'entity_id'];
        $id = $model->getKey();

        $slugs = ResolveTagsAction::withAncestors(($this->resolve)($tags));

        $replaced = match ($source) {
            TagSource::Manual => $model instanceof Chronicle
                ? [TagSource::Manual, TagSource::Curated, TagSource::Derived]
                : [TagSource::Manual],
            TagSource::Curated => [TagSource::Curated, TagSource::Derived],
            TagSource::Derived => [TagSource::Derived],
        };

        DB::transaction(function () use ($table, $key, $id, $slugs, $source, $replaced): void {
            DB::table($table)
                ->where($key, $id)
                ->whereIn('source', array_map(fn (TagSource $s): string => $s->value, $replaced))
                ->delete();

            $now = now();
            DB::table($table)->insertOrIgnore(array_map(fn (string $slug): array => [
                $key => $id,
                'tag' => $slug,
                'source' => $source->value,
                'created_at' => $now,
                'updated_at' => $now,
            ], $slugs));
        });

        return $slugs;
    }
}
