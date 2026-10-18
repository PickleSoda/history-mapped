<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use Illuminate\Database\Eloquent\Model;

/**
 * The `tags` list shared by entities and chronicles: `{slug, source}` from a `tag`/`source` row model,
 * sorted by slug. Callers must eager-load only the exported sources (TagSource::exported()).
 */
final class TagList
{
    /**
     * @param  iterable<Model>  $rows  entity_tags / chronicle_tags rows
     * @return list<array{slug: mixed, source: mixed}>
     */
    public static function build(iterable $rows): array
    {
        $items = [];
        foreach ($rows as $row) {
            $items[] = ['slug' => Values::raw($row, 'tag'), 'source' => Values::raw($row, 'source')];
        }

        return Values::sortList($items, fn (array $t) => [(string) $t['slug']]);
    }
}
