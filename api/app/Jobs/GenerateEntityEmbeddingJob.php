<?php

declare(strict_types=1);

namespace App\Jobs;

use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Generate pgvector embeddings for a batch of entities.
 *
 * Embedding text format (must match pipeline/embeddings/generator.py):
 *
 *   [entity_type] Name (alternative names)
 *   Summary text...
 *   Significance text...
 *   Tags: tag1, tag2
 *   Temporal: start — end
 *   Location: location_name
 *
 * This canonical format ensures that embeddings generated from the Python
 * pipeline and from Laravel produce identical vectors for the same content.
 */
class GenerateEntityEmbeddingJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 3;

    public int $backoff = 30;

    public int $timeout = 120;

    /**
     * @param  list<string>  $entityIds  — UUIDs of entities to embed.
     * @param  string  $model  — OpenAI model identifier.
     */
    public function __construct(
        public readonly array $entityIds,
        public readonly string $model = 'text-embedding-3-small',
    ) {}

    public function handle(): void
    {
        $apiKey = config('services.openai.api_key');

        if (! $apiKey) {
            Log::error('[Embeddings] OPENAI_API_KEY not configured');

            return;
        }

        // Load entities
        $entities = DB::table('entities')
            ->whereIn('entity_id', $this->entityIds)
            ->select([
                'entity_id', 'entity_type', 'name', 'alternative_names',
                'summary', 'significance', 'tags',
                'temporal_start', 'temporal_end', 'location_name',
            ])
            ->get();

        if ($entities->isEmpty()) {
            return;
        }

        // Build embedding texts
        $texts = [];
        $entityMap = [];  // index → entity_id

        foreach ($entities as $i => $entity) {
            $text = $this->buildEmbeddingText($entity);
            $texts[] = $text;
            $entityMap[$i] = $entity->entity_id;
        }

        // Call OpenAI Embeddings API
        try {
            $response = Http::withHeaders([
                'Authorization' => "Bearer {$apiKey}",
                'Content-Type' => 'application/json',
            ])
                ->timeout(60)
                ->post('https://api.openai.com/v1/embeddings', [
                    'model' => $this->model,
                    'input' => $texts,
                ]);

            if (! $response->successful()) {
                Log::error('[Embeddings] OpenAI API error: '.$response->body());

                throw new \RuntimeException("OpenAI API returned {$response->status()}");
            }

            $embeddings = $response->json('data');

            // Update entities with embeddings
            foreach ($embeddings as $item) {
                $index = $item['index'];
                $vector = $item['embedding'];
                $entityId = $entityMap[$index] ?? null;

                if (! $entityId) {
                    continue;
                }

                // Store as pgvector format: [0.1, 0.2, ...]
                $vectorString = '['.implode(',', $vector).']';

                DB::statement(
                    'UPDATE entities SET embedding = ?::vector, embedding_version = ? WHERE entity_id = ?',
                    [$vectorString, $this->model, $entityId]
                );
            }

            Log::info('[Embeddings] Generated embeddings for '.count($embeddings).' entities');

        } catch (\Throwable $e) {
            Log::error('[Embeddings] Failed: '.$e->getMessage());

            throw $e;
        }
    }

    /**
     * Build the embedding text for an entity.
     *
     * IMPORTANT: This format MUST match pipeline/embeddings/generator.py
     * build_embedding_text() to ensure consistent embeddings regardless
     * of which system generates them.
     */
    private function buildEmbeddingText(object $entity): string
    {
        $parts = [];

        // Type + Name header
        $header = "[{$entity->entity_type}] {$entity->name}";
        $altNames = $this->decodeArray($entity->alternative_names);

        if (! empty($altNames)) {
            $header .= ' ('.implode(', ', array_slice($altNames, 0, 5)).')';
        }
        $parts[] = $header;

        // Summary
        if ($entity->summary) {
            $parts[] = $entity->summary;
        }

        // Significance
        if ($entity->significance) {
            $parts[] = $entity->significance;
        }

        // Tags
        $tags = $this->decodeArray($entity->tags);
        if (! empty($tags)) {
            $parts[] = 'Tags: '.implode(', ', $tags);
        }

        // Temporal range
        if ($entity->temporal_start || $entity->temporal_end) {
            $parts[] = 'Temporal: '.($entity->temporal_start ?? '?').' — '.($entity->temporal_end ?? '?');
        }

        // Location
        if ($entity->location_name) {
            $parts[] = "Location: {$entity->location_name}";
        }

        return implode("\n", $parts);
    }

    /**
     * Decode a PostgreSQL text[] or JSON array column.
     *
     * @return list<string>
     */
    private function decodeArray(mixed $value): array
    {
        if (is_array($value)) {
            return $value;
        }

        if (is_string($value)) {
            // Try JSON first
            $decoded = json_decode($value, true);
            if (is_array($decoded)) {
                return $decoded;
            }

            // PostgreSQL array format: {val1,val2,val3}
            if (str_starts_with($value, '{') && str_ends_with($value, '}')) {
                return str_getcsv(trim($value, '{}'));
            }
        }

        return [];
    }
}
