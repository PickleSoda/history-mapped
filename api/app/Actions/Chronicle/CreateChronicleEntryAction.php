<?php

declare(strict_types=1);

namespace App\Actions\Chronicle;

use App\DTOs\ChronicleEntryData;
use App\Models\ChronicleEntry;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class CreateChronicleEntryAction
{
    public function __invoke(string $chronicleId, ChronicleEntryData $data, ?string $createdBy = null): ChronicleEntry
    {
        if (trim((string) $data->narrativeText) === '') {
            throw new \InvalidArgumentException('A chronicle entry requires narrative text.');
        }

        return DB::transaction(function () use ($chronicleId, $data, $createdBy): ChronicleEntry {
            $entry = ChronicleEntry::create([
                'entry_id' => (string) Str::uuid(),
                'chronicle_id' => $chronicleId,
                'narrative_text' => $data->narrativeText,
                'notes' => $data->notes,
                'primary_relationship_id' => $data->primaryRelationshipId,
                'generated_by' => $createdBy ?? 'agent',
            ]);

            if ($data->entityIds !== null) {
                $entry->secondaryEntities()->sync($data->entityIds);
            }

            return $entry;
        });
    }
}
