<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\Entity\FetchEntityImagesAction;
use App\Services\WikimediaImages;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Throwable;

/**
 * Link Wikimedia Commons images (with author/license) to entities that have a
 * Wikidata id. Nothing is downloaded. Highest-impact entities go first.
 *
 *   php artisan entity:fetch-images                 # entities not checked yet
 *   php artisan entity:fetch-images --refresh       # re-check all (admin-curated ones excepted)
 *   php artisan entity:fetch-images --entity-id=<uuid> --dry-run
 *   php artisan entity:fetch-images --report        # coverage by type, no fetching
 *
 * Entities without a Wikidata id are not matched by name (namesake risk); pick
 * their images in the admin entity editor.
 */
class FetchEntityImagesCommand extends Command
{
    protected $signature = 'entity:fetch-images
        {--entity-id=* : Only these entities}
        {--type=* : Only these entity types}
        {--limit=0 : Stop after this many entities (0 = all)}
        {--refresh : Re-check entities that already have media_refs}
        {--dry-run : Print what would be stored; write nothing}
        {--report : Only print image coverage by entity type}';

    protected $description = 'Link Wikimedia Commons images and their licenses to entities with a Wikidata id';

    public function handle(FetchEntityImagesAction $fetch): int
    {
        if ($this->option('report')) {
            $this->report();

            return self::SUCCESS;
        }

        $limit = (int) $this->option('limit');
        $entities = DB::table('entities')
            ->whereNotNull('wikidata_id')
            ->whereRaw('attributes -> ? IS NULL', [FetchEntityImagesAction::CURATED_KEY])
            ->when(! $this->option('refresh'), fn ($q) => $q->whereRaw("attributes -> 'media_refs' IS NULL"))
            ->when($this->option('entity-id'), fn ($q, $ids) => $q->whereIn('entity_id', $ids))
            ->when($this->option('type'), fn ($q, $types) => $q->whereIn('entity_type', $types))
            ->orderByDesc(DB::raw('COALESCE(impact_score, 0)'))
            ->orderBy('entity_id')
            ->when($limit > 0, fn ($q) => $q->limit($limit))
            ->get(['entity_id', 'name', 'wikidata_id', 'entity_type']);

        if ($entities->isEmpty()) {
            $this->components->info('Nothing to fetch.');

            return self::SUCCESS;
        }

        $found = 0;
        $none = 0;
        $failed = 0;
        $bar = $this->option('dry-run') ? null : $this->output->createProgressBar($entities->count());

        foreach ($entities->chunk(WikimediaImages::BATCH) as $chunk) {
            try {
                $media = $fetch->find($chunk);
            } catch (Throwable $e) {
                // Leave the batch unchecked so the next run retries it.
                $failed += $chunk->count();
                $this->newLine();
                $this->components->warn($e->getMessage());
                $bar?->advance($chunk->count());

                continue;
            }

            foreach ($media as $items) {
                $items === [] ? $none++ : $found++;
            }

            if ($this->option('dry-run')) {
                foreach ($chunk as $entity) {
                    $items = $media[$entity->entity_id] ?? [];
                    $this->line(sprintf(
                        '%s (%s): %s',
                        $entity->name,
                        $entity->wikidata_id,
                        $items === [] ? '—' : implode(', ', array_map(fn ($i) => "{$i['kind']} {$i['file']} [{$i['license']}]", $items)),
                    ));
                }
            } else {
                $fetch->save($media);
                $bar?->advance($chunk->count());
            }
        }

        $bar?->finish();
        $this->newLine(2);
        $this->components->twoColumnDetail('With images', (string) $found);
        $this->components->twoColumnDetail('Nothing on Wikimedia', (string) $none);
        if ($failed > 0) {
            $this->components->twoColumnDetail('<fg=yellow>Failed (retried next run)</>', (string) $failed);
        }

        return $failed > 0 ? self::FAILURE : self::SUCCESS;
    }

    private function report(): void
    {
        $rows = DB::select(<<<'SQL'
            SELECT entity_type,
                   count(*) AS total,
                   count(*) FILTER (WHERE n > 0) AS with_image,
                   count(*) FILTER (WHERE n = 0 AND wikidata_id IS NOT NULL AND attributes -> 'media_refs' IS NOT NULL) AS none_on_wikimedia,
                   count(*) FILTER (WHERE n = 0 AND wikidata_id IS NOT NULL AND attributes -> 'media_refs' IS NULL) AS unchecked,
                   count(*) FILTER (WHERE n = 0 AND wikidata_id IS NULL) AS no_qid
            FROM (
                SELECT entity_type, wikidata_id, attributes,
                       CASE WHEN jsonb_typeof(attributes->'media_refs') = 'array'
                            THEN jsonb_array_length(attributes->'media_refs') ELSE 0 END AS n
                FROM entities
            ) e
            GROUP BY entity_type
            ORDER BY total DESC
            SQL);

        $totals = ['total' => 0, 'with_image' => 0, 'none_on_wikimedia' => 0, 'unchecked' => 0, 'no_qid' => 0];
        $table = [];
        foreach ($rows as $row) {
            $table[] = (array) $row;
            foreach ($totals as $k => $v) {
                $totals[$k] = $v + $row->{$k};
            }
        }
        $table[] = ['entity_type' => '<options=bold>all</>', ...$totals];

        $this->table(['Type', 'Entities', 'With image', 'None on Wikimedia', 'Not checked yet', 'No Wikidata id'], $table);
        $this->line('Entities without an image can get one in the admin editor (Images panel): Wikidata, Wikipedia, Commons search or a pasted URL.');
    }
}
