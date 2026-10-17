<?php

declare(strict_types=1);

namespace App\Actions\Tag;

use App\Enums\TagFacet;
use App\Models\Tag;
use Illuminate\Support\Str;

/**
 * Turn free-form tag input (slugs or display names) into vocabulary slugs.
 *
 * Matching order: exact slug, case-insensitive name, slugified input. Anything
 * still unknown becomes a new Topic tag, so admins and the pipeline can tag
 * freely without editing the vocabulary first.
 */
class ResolveTagsAction
{
    /**
     * @param  iterable<mixed>  $values
     * @return list<string> unique slugs, in input order
     */
    public function __invoke(iterable $values): array
    {
        $inputs = [];
        foreach ($values as $value) {
            if (is_string($value) && trim($value) !== '') {
                $inputs[] = trim($value);
            }
        }

        if ($inputs === []) {
            return [];
        }

        $known = Tag::query()->get(['slug', 'name']);
        $bySlug = $known->pluck('slug', 'slug');
        $byName = $known->mapWithKeys(fn (Tag $t): array => [mb_strtolower($t->name) => $t->slug]);

        $slugs = [];
        foreach ($inputs as $input) {
            $slug = $bySlug[$input]
                ?? $byName[mb_strtolower($input)]
                ?? $bySlug[Str::slug($input)]
                ?? null;

            if ($slug === null) {
                $slug = Str::slug($input);
                if ($slug === '') {
                    continue;
                }

                Tag::query()->firstOrCreate(['slug' => $slug], [
                    'name' => $input,
                    'facet' => TagFacet::Topic,
                ]);
                $bySlug[$slug] = $slug;
            }

            $slugs[$slug] = true;
        }

        return array_keys($slugs);
    }

    /**
     * Add every ancestor of the given slugs (tagging "china" implies
     * "east-asia" and "asia").
     *
     * @param  list<string>  $slugs
     * @return list<string>
     */
    public static function withAncestors(array $slugs): array
    {
        $parents = Tag::query()->whereNotNull('parent_slug')->pluck('parent_slug', 'slug');

        $closure = [];
        foreach ($slugs as $slug) {
            for ($s = $slug; $s !== null && ! isset($closure[$s]); $s = $parents[$s] ?? null) {
                $closure[$s] = true;
            }
        }

        return array_keys($closure);
    }
}
