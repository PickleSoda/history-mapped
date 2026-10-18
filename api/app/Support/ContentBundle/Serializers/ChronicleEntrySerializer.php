<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use App\Models\ChronicleEntry;
use App\Models\ChronicleEntryEntity;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\Relation;

/**
 * Chronicle entry -> bundle line. Linked entities come straight from `chronicle_entry_entities`
 * (one eager-load query); `Entity` models are never hydrated.
 */
final class ChronicleEntrySerializer implements RecordSerializer
{
    private const COLUMNS = [
        'entry_id', 'chronicle_id', 'sequence_order', 'start_year', 'end_year', 'impact_score',
        'primary_relationship_id', 'narrative_text', 'notes', 'approximate_location', 'source_evidence',
        'generated_by',
    ];

    public function type(): RecordType
    {
        return RecordType::ChronicleEntries;
    }

    public function query(): Builder
    {
        return ChronicleEntry::query()
            ->select((new ChronicleEntry)->qualifyColumns(self::COLUMNS))
            ->with(['entityLinks' => fn (Relation $q) => $q->select($q->getModel()->qualifyColumns(['entry_id', ...RecordType::ChronicleEntries->nestedKeys()['entities']]))]);
    }

    public function serialize(Model $model, Profile $profile): array
    {
        assert($model instanceof ChronicleEntry);
        $r = fn (string $col) => Values::raw($model, $col);

        return [
            'id' => $r('entry_id'),
            'chronicle_id' => $r('chronicle_id'),
            'sequence_order' => $r('sequence_order'),
            'start_year' => $r('start_year'),
            'end_year' => $r('end_year'),
            'impact_score' => $r('impact_score'),
            'primary_relationship_id' => $r('primary_relationship_id'),
            'narrative_text' => $r('narrative_text'),
            'notes' => $r('notes'),
            'approximate_location' => Values::jsonbObject($model, 'approximate_location'),
            // Exactly as stored: a JSON string in every current row, but any JSON value is allowed.
            'source_evidence' => Values::jsonb($model, 'source_evidence'),
            'generated_by' => $r('generated_by'),
            'entities' => $this->entities($model),
        ];
    }

    /** @return list<array<string, mixed>> */
    private function entities(ChronicleEntry $entry): array
    {
        $items = $entry->entityLinks->map(fn (ChronicleEntryEntity $l) => [
            'entity_id' => Values::raw($l, 'entity_id'),
            'role' => Values::raw($l, 'role'),
            'sequence_in_entry' => Values::raw($l, 'sequence_in_entry'),
        ])->all();

        // Null sequences sort last.
        return Values::sortList($items, fn (array $i) => [$i['sequence_in_entry'] === null, $i['sequence_in_entry'] ?? 0, (string) $i['entity_id']]);
    }
}
