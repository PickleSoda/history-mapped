<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Models\MapStory;
use App\Support\MapStory\MapStoryDocument;
use App\Support\MapStory\MapStoryFile;
use App\Support\MapStory\MapStoryWarnings;
use stdClass;

/**
 * A dry run of SaveMapStoryAction's checks: the errors that would block a
 * save (structure, slug, atlas references) and the plausibility warnings.
 * Writes nothing.
 */
class CheckMapStoryAction
{
    public function __construct(private ResolveMapStoryAction $resolve) {}

    /** @return array{errors: list<string>, warnings: list<string>} */
    public function __invoke(stdClass $document, ?MapStory $story = null): array
    {
        return self::check($document, $story, $this->resolve);
    }

    /** @return array{errors: list<string>, warnings: list<string>} */
    public static function check(stdClass $document, ?MapStory $story, ResolveMapStoryAction $resolve): array
    {
        $doc = MapStoryFile::normaliseMaps(MapStoryFile::authored($document));
        $array = MapStoryFile::toArray($doc);
        $errors = self::structuralErrors($array, $story);
        if ($errors === []) {
            $errors = $resolve($doc)['errors'];
        }

        return ['errors' => $errors, 'warnings' => $errors === [] ? MapStoryWarnings::of($array) : []];
    }

    /**
     * MapStoryDocument's errors, plus the slug: a story keeps its own (it
     * names the file), and a new one needs a free one.
     *
     * @param  array<string, mixed>  $array
     * @return list<string>
     */
    public static function structuralErrors(array $array, ?MapStory $story): array
    {
        $errors = MapStoryDocument::errors($array);
        $slug = $array['slug'] ?? null;
        if ($story !== null && $slug !== $story->slug) {
            $errors[] = "slug: '".(is_string($slug) ? $slug : '')."' — a story keeps its slug '{$story->slug}' (it names the file); create a new story instead";
        } elseif ($story === null && is_string($slug) && MapStory::query()->where('slug', $slug)->exists()) {
            $errors[] = "slug: '{$slug}' is taken";
        }

        return $errors;
    }
}
