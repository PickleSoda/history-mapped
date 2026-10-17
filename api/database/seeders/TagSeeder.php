<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Actions\Tag\SyncTagVocabularyAction;
use Illuminate\Database\Seeder;

/**
 * The controlled tag vocabulary (database/data/tags/vocabulary.json). Tagging
 * existing chronicles and entities is `php artisan tags:sync`, not a seed.
 */
class TagSeeder extends Seeder
{
    public function run(SyncTagVocabularyAction $syncVocabulary): void
    {
        $syncVocabulary();
    }
}
