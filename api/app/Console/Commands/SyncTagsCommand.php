<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\Tag\DeriveTagsAction;
use App\Actions\Tag\SyncTagsAction;
use App\Actions\Tag\SyncTagVocabularyAction;
use App\Enums\TagSource;
use App\Models\Chronicle;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

/**
 * Load the tag vocabulary, apply the curated chronicle tags and recompute every
 * derived tag. Idempotent; safe to re-run after each content import.
 *
 *   php artisan tags:sync
 *   php artisan tags:sync --vocabulary-only
 *
 * Chronicles an admin has tagged (any Manual row) keep their tags untouched.
 */
class SyncTagsCommand extends Command
{
    public const CURATED_PATH = 'data/tags/chronicles.json';

    protected $signature = 'tags:sync
        {--vocabulary-only : Only upsert the vocabulary; skip chronicle and entity tagging}';

    protected $description = 'Sync the tag vocabulary, curated chronicle tags and derived chronicle/entity tags';

    public function handle(
        SyncTagVocabularyAction $syncVocabulary,
        SyncTagsAction $syncTags,
        DeriveTagsAction $deriveTags,
    ): int {
        $vocabulary = $syncVocabulary();
        $this->components->twoColumnDetail('Vocabulary', "{$vocabulary['upserted']} upserted, {$vocabulary['deleted']} removed");

        if ($this->option('vocabulary-only')) {
            return self::SUCCESS;
        }

        $curated = json_decode((string) file_get_contents(database_path(self::CURATED_PATH)), true, flags: JSON_THROW_ON_ERROR)['chronicles'];

        $manual = DB::table('chronicle_tags')
            ->where('source', TagSource::Manual->value)
            ->distinct()
            ->pluck('chronicle_id')
            ->flip();

        $applied = 0;
        $skipped = 0;
        $chronicles = Chronicle::query()->whereIn('slug', array_keys($curated))->get(['chronicle_id', 'slug']);
        foreach ($chronicles as $chronicle) {
            if (isset($manual[$chronicle->chronicle_id])) {
                $skipped++;

                continue;
            }

            $syncTags($chronicle, $curated[$chronicle->slug], TagSource::Curated);
            $applied++;
        }
        $unknown = array_diff(array_keys($curated), $chronicles->pluck('slug')->all());

        $this->components->twoColumnDetail('Curated chronicles', "{$applied} applied, {$skipped} kept (admin-edited), ".count($unknown).' not in DB');

        $derived = $deriveTags();
        $this->components->twoColumnDetail('Derived chronicle tags', (string) $derived['chronicle_tags']);
        $this->components->twoColumnDetail('Derived entity tags', (string) $derived['entity_tags']);

        $untagged = Chronicle::query()->whereDoesntHave('tags')->count();
        if ($untagged > 0) {
            $this->warn("{$untagged} chronicle(s) have no tags (no curated entry and no dates). Tag them in the admin.");
        }

        return self::SUCCESS;
    }
}
