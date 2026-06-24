<?php

declare(strict_types=1);

namespace App\Actions\Chronicle;

use App\DTOs\ChronicleEntryData;
use App\Models\ChronicleEntry;
use Illuminate\Support\Facades\DB;

class UpdateChronicleEntryAction
{
    public function __invoke(ChronicleEntry $entry, ChronicleEntryData $data): ChronicleEntry
    {
        return DB::transaction(function () use ($entry, $data): ChronicleEntry {
            $entry->fill(array_filter([
                'narrative_text' => $data->narrativeText,
                'notes' => $data->notes,
                'primary_relationship_id' => $data->primaryRelationshipId,
            ], fn ($v) => $v !== null));
            $entry->save();

            if ($data->entityIds !== null) {
                $entry->secondaryEntities()->sync($data->entityIds);
            }

            return $entry->refresh();
        });
    }
}
