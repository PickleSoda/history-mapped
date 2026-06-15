<?php

declare(strict_types=1);

namespace App\Actions\Chronicle;

use App\DTOs\ChronicleData;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\EntityRelationship;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class UpdateChronicleAction
{
    public function __invoke(Chronicle $chronicle, ChronicleData $data): Chronicle
    {
        return DB::transaction(function () use ($chronicle, $data): Chronicle {
            $modelData = $data->toModelArray();

            // Remove fields that shouldn't be mass-updated
            unset($modelData['chronicle_id'], $modelData['created_by']);

            // Auto-regenerate slug from title if title changed and slug not explicitly provided
            if ($data->slug === null && $chronicle->title !== $data->title) {
                $modelData['slug'] = Str::slug($data->title);
            }

            $chronicle->update($modelData);

            // Replace entries: delete existing and recreate
            if ($data->entries !== null) {
                ChronicleEntry::where('chronicle_id', $chronicle->chronicle_id)->delete();
                $this->syncEntries($chronicle, $data->entries);
                // Fill derived impact_score / approximate_location (+ aggregate to
                // the chronicle) from the freshly-attached relationships + entities.
                app(EnrichChronicleMetadataAction::class)($chronicle);
            }

            return $chronicle->fresh();
        });
    }

    /**
     * Sync chronicle entries from DTO entries array.
     *
     * @param  list<array<string, mixed>>  $entriesData
     */
    private function syncEntries(Chronicle $chronicle, array $entriesData): void
    {
        foreach ($entriesData as $entryData) {
            $entryId = (string) Str::uuid();

            $entry = ChronicleEntry::create([
                'entry_id' => $entryId,
                'chronicle_id' => $chronicle->chronicle_id,
                'sequence_order' => $entryData['sequence_order'] ?? 0,
                'start_year' => $entryData['start_year'] ?? null,
                'end_year' => $entryData['end_year'] ?? null,
                'impact_score' => $entryData['impact_score'] ?? null,
                'approximate_location' => $entryData['approximate_location'] ?? null,
                'primary_relationship_id' => $this->resolvePrimaryRelationshipId($entryData),
                'narrative_text' => $entryData['narrative_text'] ?? '',
                'notes' => $entryData['notes'] ?? null,
                'source_evidence' => $entryData['source_evidence'] ?? null,
            ]);

            if (! empty($entryData['secondary_entity_ids']) && is_array($entryData['secondary_entity_ids'])) {
                $pivotData = [];
                foreach ($entryData['secondary_entity_ids'] as $index => $entityId) {
                    $pivotData[$entityId] = [
                        'role' => $entryData['secondary_roles'][$index] ?? 'mentioned',
                        'sequence_in_entry' => $index,
                    ];
                }
                $entry->secondaryEntities()->attach($pivotData);
            }
        }
    }

    /**
     * Resolve an entry's primary relationship.
     *
     * An explicit primary_relationship_id wins. Otherwise, if the entry carries
     * a `new_relationship` spec (source/target/type — the chronicle editor's way
     * of authoring relationships), find-or-create that relationship and use its
     * id, so editing a chronicle can generate real relationship rows.
     *
     * @param  array<string, mixed>  $entryData
     */
    private function resolvePrimaryRelationshipId(array $entryData): ?string
    {
        $existing = $entryData['primary_relationship_id'] ?? null;
        if (is_string($existing) && $existing !== '') {
            return $existing;
        }

        $spec = $entryData['new_relationship'] ?? null;
        if (! is_array($spec)) {
            return null;
        }

        $source = $spec['source_entity_id'] ?? null;
        $target = $spec['target_entity_id'] ?? null;
        $type = $spec['relationship_type'] ?? null;
        if (! is_string($source) || ! is_string($target) || ! is_string($type) || $source === '' || $target === '' || $type === '') {
            return null;
        }

        $relationship = EntityRelationship::query()
            ->where('source_entity_id', $source)
            ->where('target_entity_id', $target)
            ->where('relationship_type', $type)
            ->first();

        if ($relationship === null) {
            $relationship = EntityRelationship::create([
                'source_entity_id' => $source,
                'target_entity_id' => $target,
                'relationship_type' => $type,
                'created_by' => 'chronicle-admin',
            ]);
        }

        return $relationship->relationship_id;
    }
}
