<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Actions\Relationship\CreateRelationshipAction;
use App\DTOs\RelationshipData;
use App\Enums\ConfidenceLevel;
use App\Enums\RelationshipType;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

/**
 * Resolve pipeline relationship hints into actual relationship records.
 *
 * After entities are imported, this job reads the pipeline_relationship_hints
 * staging table and creates relationship records by matching target_wikidata_id
 * to existing entities.
 *
 * Each hint is resolved through CreateRelationshipAction so that auto-snapshot
 * logic fires correctly for applicable relationship types (e.g. born_in,
 * fought_at, signed_by).
 *
 * Dedup strategy for relationships:
 * - Unique on (source_entity_id, target_entity_id, relationship_type)
 * - Symmetric relationships (married_to, allied_with, etc.) check both directions
 * - Temporal overlap is NOT checked (two entities can have the same relationship
 *   type at different time periods — e.g., allied then at war)
 */
class ResolveRelationshipsJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 1;

    public int $timeout = 600;

    /**
     * Relationship types that are symmetric — i.e. A→B and B→A represent the
     * same real-world fact. Dedup checks both directions for these.
     *
     * @var list<string>
     */
    private const SYMMETRIC_TYPES = [
        'married_to',
        'allied_with',
        'sibling_of',
        'trades_with',
        'at_war_with',
    ];

    public function __construct(
        public readonly string $batchId,
    ) {}

    public function handle(CreateRelationshipAction $createRelationship): void
    {
        Log::info("[Pipeline] Resolving relationships for batch: {$this->batchId}");

        if ($this->hasStagingTable()) {
            $this->resolveFromStagingTable($createRelationship);
        } else {
            $this->resolveFromEntityAttributes($createRelationship);
        }
    }

    /**
     * Check if the staging table exists.
     */
    private function hasStagingTable(): bool
    {
        try {
            return DB::getSchemaBuilder()->hasTable('pipeline_relationship_hints');
        } catch (\Throwable) {
            return false;
        }
    }

    /**
     * Resolve from the dedicated staging table.
     *
     * Iterates all unresolved hints for this batch, looks up the target entity
     * by wikidata_id, validates the relationship type against the enum, and
     * delegates creation to CreateRelationshipAction (which handles auto-snapshots).
     */
    private function resolveFromStagingTable(CreateRelationshipAction $createRelationship): void
    {
        $hints = DB::table('pipeline_relationship_hints')
            ->where('batch_id', $this->batchId)
            ->where('resolved', false)
            ->get();

        Log::info("[Pipeline] Found {$hints->count()} unresolved relationship hints");

        $created = 0;
        $skipped = 0;
        $unresolvable = 0;

        foreach ($hints as $hint) {
            // Validate the relationship type before touching the DB
            $type = RelationshipType::tryFrom($hint->relationship_type);

            if ($type === null) {
                Log::debug("[Pipeline] Unknown relationship type '{$hint->relationship_type}', skipping hint {$hint->id}");
                $this->markHint($hint->id, 'unknown_type');
                $skipped++;

                continue;
            }

            // Look up target entity by wikidata_id
            $targetEntity = DB::table('entities')
                ->where('wikidata_id', $hint->target_wikidata_id)
                ->value('entity_id');

            if ($targetEntity === null) {
                $this->markHint($hint->id, 'target_not_found');
                $unresolvable++;

                continue;
            }

            // Self-reference guard
            if ($hint->source_entity_id === $targetEntity) {
                $this->markHint($hint->id, 'self_reference');
                $skipped++;

                continue;
            }

            // Dedup: skip if this relationship already exists
            if ($this->relationshipExists($hint->source_entity_id, $targetEntity, $hint->relationship_type)) {
                $this->markHint($hint->id, 'already_exists');
                $skipped++;

                continue;
            }

            try {
                $citations = $this->buildCitations($hint->wikidata_property ?? null);

                $data = new RelationshipData(
                    sourceEntityId: $hint->source_entity_id,
                    targetEntityId: $targetEntity,
                    relationshipType: $type,
                    confidence: ConfidenceLevel::tryFrom($hint->confidence ?? '') ?? ConfidenceLevel::Medium,
                    sourceCitations: $citations,
                );

                $createRelationship($data, "pipeline:{$this->batchId}");

                $this->markHint($hint->id, 'created');
                $created++;

            } catch (\Throwable $e) {
                Log::warning("[Pipeline] Failed to create relationship for hint {$hint->id}: {$e->getMessage()}", [
                    'source' => $hint->source_entity_id,
                    'target' => $targetEntity,
                    'type' => $hint->relationship_type,
                ]);
            }
        }

        Log::info(
            "[Pipeline] Relationships resolved: {$created} created, "
            ."{$skipped} skipped (dedup/invalid), {$unresolvable} unresolvable (target not in DB)"
        );
    }

    /**
     * Fallback path: resolve hints stored in entity attributes JSONB.
     *
     * Used when the pipeline_relationship_hints staging table is unavailable
     * (e.g. a migration has not been run in a non-standard environment).
     */
    private function resolveFromEntityAttributes(CreateRelationshipAction $createRelationship): void
    {
        $entities = DB::table('entities')
            ->whereRaw('jsonb_exists(attributes, ?)', ['_relationship_hints'])
            ->where(function ($query): void {
                $query
                    ->whereRaw("attributes->>'_relationship_hints_batch' = ?", [$this->batchId])
                    // Legacy fallback hints (from before batch tagging) must still be processed.
                    ->orWhereRaw('NOT jsonb_exists(attributes, ?)', ['_relationship_hints_batch']);
            })
            ->select('entity_id', 'attributes')
            ->get();

        Log::info("[Pipeline] Found {$entities->count()} entities with embedded relationship hints");

        $created = 0;

        foreach ($entities as $entity) {
            $attributes = json_decode($entity->attributes, true) ?? [];
            $hints = $attributes['_relationship_hints'] ?? [];

            foreach ($hints as $hint) {
                $type = RelationshipType::tryFrom($hint['relationship_type'] ?? '');

                if ($type === null) {
                    continue;
                }

                $targetId = DB::table('entities')
                    ->where('wikidata_id', $hint['target_wikidata_id'] ?? null)
                    ->value('entity_id');

                if ($targetId === null || $entity->entity_id === $targetId) {
                    continue;
                }

                if ($this->relationshipExists($entity->entity_id, $targetId, $hint['relationship_type'])) {
                    continue;
                }

                try {
                    $data = new RelationshipData(
                        sourceEntityId: $entity->entity_id,
                        targetEntityId: $targetId,
                        relationshipType: $type,
                        confidence: ConfidenceLevel::tryFrom($hint['confidence'] ?? '') ?? ConfidenceLevel::Medium,
                    );

                    $createRelationship($data, "pipeline:{$this->batchId}");
                    $created++;

                } catch (\Throwable) {
                    // Skip failed relationships silently in the fallback path
                }
            }

            // Clean up hints from attributes after processing
            DB::table('entities')
                ->where('entity_id', $entity->entity_id)
                ->update([
                    'attributes' => DB::raw("attributes - '_relationship_hints' - '_relationship_hints_batch'"),
                ]);
        }

        Log::info("[Pipeline] Created {$created} relationships from embedded hints");
    }

    /**
     * Mark a single hint row as resolved with the given note.
     */
    private function markHint(int $hintId, string $note): void
    {
        DB::table('pipeline_relationship_hints')
            ->where('id', $hintId)
            ->update(['resolved' => true, 'resolution_note' => $note]);
    }

    /**
     * Check if a relationship already exists (either direction for symmetric types).
     */
    private function relationshipExists(string $sourceId, string $targetId, string $type): bool
    {
        $exists = DB::table('relationships')
            ->where('source_entity_id', $sourceId)
            ->where('target_entity_id', $targetId)
            ->where('relationship_type', $type)
            ->exists();

        if ($exists) {
            return true;
        }

        if (in_array($type, self::SYMMETRIC_TYPES, true)) {
            return DB::table('relationships')
                ->where('source_entity_id', $targetId)
                ->where('target_entity_id', $sourceId)
                ->where('relationship_type', $type)
                ->exists();
        }

        return false;
    }

    /**
     * Build a source_citations array from a Wikidata property ID.
     *
     * Returns null (no citations) when no property is available, rather than
     * storing a meaningless placeholder.
     *
     * @return list<array<string, string>>|null
     */
    private function buildCitations(?string $wikidataProperty): ?array
    {
        if ($wikidataProperty === null || $wikidataProperty === '') {
            return null;
        }

        return [[
            'source_type' => 'reference',
            'title' => "Wikidata property: {$wikidataProperty}",
            'reliability' => 'reference',
        ]];
    }
}
