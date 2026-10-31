<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\MapStory\ExportMapStoryAction;
use App\Models\MapStory;
use Illuminate\Console\Command;

/**
 * Write map stories from the database to resources/map-stories/<slug>.json
 * in the pipeline builder's exact format, so what humans and the AI edited
 * can be committed. Afterwards `map-stories:sync` is a no-op for them.
 *
 *   php artisan map-stories:export --edited          # only stories with unexported edits
 *   php artisan map-stories:export --slug=battle-of-cannae
 *   php artisan map-stories:export                   # every story
 *
 * The builder (`python -m pipeline.map_stories build`) then refuses to
 * overwrite an exported file without --force: port the edits into the
 * builder module first. See docs/implementation-docs/map-story-authoring.md.
 */
class ExportMapStoriesCommand extends Command
{
    protected $signature = 'map-stories:export
        {--slug=* : Only export these slugs}
        {--edited : Only stories edited since their file was last synced or exported}
        {--path= : Write to this directory instead of resources/map-stories}';

    protected $description = 'Write map stories from the database to resources/map-stories (the builder format)';

    public function handle(ExportMapStoryAction $export): int
    {
        $query = MapStory::query()->orderBy('slug');
        $only = array_values(array_filter((array) $this->option('slug')));
        if ($only !== []) {
            $query->whereIn('slug', $only);
        }
        if ($this->option('edited')) {
            $query->edited();
        }

        $count = 0;
        foreach ($query->get() as $story) {
            $result = $export($story, $this->option('path') ?: null);
            $this->components->twoColumnDetail($story->slug, $result['status']);
            $count++;
        }
        if ($count === 0) {
            $this->components->info('Nothing to export.');
        }

        return self::SUCCESS;
    }
}
