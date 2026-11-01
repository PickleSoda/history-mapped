<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Console\Commands\SyncMapStoriesCommand;
use App\Models\MapStory;
use App\Support\MapStory\MapStoryFile;

/**
 * Write a story's document to `<directory>/<slug>.json` in the builder's exact
 * format (MapStoryFile::encode: the authored document, without the ids sync
 * resolved, key order as stored), and record the file as in sync with the row
 * (`file_hash`, `synced_at`, `source_path`). A file that already holds those
 * bytes is not rewritten. A developer then commits what humans and the AI
 * edited; the pipeline builder refuses to overwrite it (see
 * pipeline/map_stories/__main__.py).
 */
class ExportMapStoryAction
{
    /** @return array{status: 'written'|'unchanged', path: string} */
    public function __invoke(MapStory $story, ?string $directory = null): array
    {
        $directory = rtrim($directory ?? resource_path(SyncMapStoriesCommand::DIRECTORY), '/');
        $path = "{$directory}/{$story->slug}.json";
        $content = MapStoryFile::encode(MapStoryFile::authored($story->document));

        $unchanged = is_file($path) && file_get_contents($path) === $content;
        if (! $unchanged) {
            if (! is_dir($directory)) {
                mkdir($directory, 0775, true);
            }
            file_put_contents($path, $content);
        }

        $story->forceFill([
            'file_hash' => MapStoryFile::hash($content),
            'synced_at' => now(),
            'source_path' => 'resources/'.SyncMapStoriesCommand::DIRECTORY.'/'.$story->slug.'.json',
        ])->save();

        return ['status' => $unchanged ? 'unchanged' : 'written', 'path' => $path];
    }
}
