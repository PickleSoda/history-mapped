<?php

declare(strict_types=1);

namespace App\Actions\Chronicle;

use App\DTOs\ChronicleData;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class CreateChronicleAction
{
    public function __invoke(ChronicleData $data, ?string $createdBy = null): Chronicle
    {
        return DB::transaction(function () use ($data, $createdBy): Chronicle {
            $modelData = $data->toModelArray();

            $chronicleId = (string) Str::uuid();
            $modelData['chronicle_id'] = $chronicleId;

            if ($createdBy !== null) {
                $modelData['created_by'] = $createdBy;
            }

            // Auto-generate slug from title if not provided
            if (empty($modelData['slug'])) {
                $modelData['slug'] = Str::slug($data->title);
            }

            $chronicle = Chronicle::create($modelData);

            $this->syncEntries($chronicle, $data->entries);

            return $chronicle->fresh();
        });
    }

    /**
     * Sync chronicle entries from DTO entries array.
     *
     * @param  list<array<string, mixed>>|null  $entriesData
     */
    private function syncEntries(Chronicle $chronicle, ?array $entriesData): void
    {
        if ($entriesData === null) {
            return;
        }

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
                'primary_relationship_id' => $entryData['primary_relationship_id'] ?? null,
                'narrative_text' => $entryData['narrative_text'] ?? '',
                'notes' => $entryData['notes'] ?? null,
                'source_evidence' => $entryData['source_evidence'] ?? null,
            ]);

            if (!empty($entryData['secondary_entity_ids']) && is_array($entryData['secondary_entity_ids'])) {
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
}
