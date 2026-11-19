<?php

namespace Tests\Feature\Persona;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/** Builders shared by the "Talk with people" tests. */
trait PersonaTestHelpers
{
    protected function person(string $name = 'Marcus Test', int $born = 1700, ?int $died = 1760, int $impact = 70): Entity
    {
        $factory = Entity::factory()->ofType(EntityType::Person);
        if ($died !== null) {
            $factory = $factory->withTemporalRange((string) $born, (string) $died);
        }

        return $factory->create([
            'name' => $name,
            'summary' => "{$name} was a test figure.",
            'impact_score' => $impact,
            'attributes' => ['roles' => ['general', 'statesman']],
        ]);
    }

    protected function thing(EntityType $type, string $name, ?int $start, ?int $end = null, int $impact = 60): Entity
    {
        $factory = Entity::factory()->ofType($type);
        if ($start !== null) {
            $factory = $factory->withTemporalRange((string) $start, (string) ($end ?? $start));
        }

        return $factory->create(['name' => $name, 'impact_score' => $impact, 'summary' => null, 'attributes' => []]);
    }

    protected function link(Entity $from, string $type, Entity $to, ?int $start = null, ?int $end = null): void
    {
        DB::table('relationships')->insert([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $from->entity_id,
            'target_entity_id' => $to->entity_id,
            'relationship_type' => $type,
            'temporal_start' => $start === null ? null : (string) $start,
            'temporal_end' => $end === null ? null : (string) $end,
            'created_at' => now(),
        ]);
    }

    protected function place(Entity $entity, float $lon, float $lat): void
    {
        DB::statement(
            'INSERT INTO entity_locations (location_id, entity_id, location_name, geom, is_primary, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, ?, ST_SetSRID(ST_MakePoint(?, ?), 4326), true, now(), now())',
            [$entity->entity_id, $entity->name, $lon, $lat],
        );
    }

    protected function chronicleEntry(Entity $about, int $year, string $text): void
    {
        $chronicle = Chronicle::factory()->published()->create();
        $entry = ChronicleEntry::factory()->create([
            'chronicle_id' => $chronicle->chronicle_id,
            'narrative_text' => $text,
            'start_year' => $year,
            'end_year' => $year,
            'impact_score' => 80,
        ]);
        DB::table('chronicle_entry_entities')->insert(['entry_id' => $entry->entry_id, 'entity_id' => $about->entity_id, 'role' => 'participant']);
    }

    /** A persona JSON the writer agent returns. */
    protected function personaJson(): string
    {
        return json_encode([
            'voice' => 'Dry and exact, a soldier who dislikes ornament.',
            'temperament' => ['proud', 'impatient'],
            'values' => ['duty', 'loyalty'],
            'cares_about' => ['his legions'],
            'speech_habits' => ['short orders'],
            'self_view' => 'A servant of the state.',
            'address_to_acquaintance' => 'Calls the visitor friend.',
            'language_note' => 'Answer in the visitor language with period flavour.',
        ]);
    }
}
