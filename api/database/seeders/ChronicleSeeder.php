<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Enums\EntityGroup;
use App\Enums\EntityType;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class ChronicleSeeder extends Seeder
{
    public function run(array $parameters = []): void
    {
        $this->command->info('Seeding chronicles...');

        // ── Chronicle 1: Battle of Didgori (1121) ─────────────
        $didgoriId = Str::uuid()->toString();
        DB::table('chronicles')->insert([
            'chronicle_id' => $didgoriId,
            'title' => 'Battle of Didgori',
            'slug' => 'battle-of-didgori',
            'source_type' => 'article',
            'source_reference' => 'The Georgian Chronicle, Vol. II',
            'status' => 'published',
            'metadata' => json_encode([
                'year' => 1121,
                'location' => 'Didgori, Georgia',
                'outcome' => 'Decisive Georgian victory',
            ]),
            'created_by' => 'seeder',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        // Create a dummy relationship for the primary_relationship_id
        $relId = Str::uuid()->toString();
        $davidId = $this->findOrCreateEntity('David IV', 'person');
        $ilghaziId = $this->findOrCreateEntity('Ilghazi', 'person');

        DB::table('relationships')->insert([
            'relationship_id' => $relId,
            'source_entity_id' => $davidId,
            'target_entity_id' => $ilghaziId,
            'relationship_type' => 'victorious_at',
            'temporal_start' => '1121-08-12',
            'temporal_end' => '1121-08-12',
            'start_year' => 1121,
            'end_year' => 1121,
            'created_by' => 'seeder',
            'created_at' => now(),
        ]);

        $entry1Id = Str::uuid()->toString();
        DB::table('chronicle_entries')->insert([
            'entry_id' => $entry1Id,
            'chronicle_id' => $didgoriId,
            'sequence_order' => 0,
            'primary_relationship_id' => $relId,
            'narrative_text' => 'In August 1121, David IV of Georgia confronted the Seljuk army under Ilghazi near Didgori. The Georgian forces, bolstered by Kipchak mercenaries, achieved a decisive victory on August 12, shattering Seljuk dominance in the region.',
            'notes' => 'The battle is considered the turning point in Georgia\'s Golden Age.',
            'source_evidence' => json_encode(['medieval chronicle']),
            'generated_by' => 'seeder',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        // ── Chronicle 2: Roman Civil Wars ───────────────────────
        $romanId = Str::uuid()->toString();
        DB::table('chronicles')->insert([
            'chronicle_id' => $romanId,
            'title' => 'Roman Civil Wars',
            'slug' => 'roman-civil-wars',
            'source_type' => 'book_excerpt',
            'source_reference' => 'Appian, Civil Wars',
            'status' => 'draft',
            'metadata' => json_encode([
                'period' => '49 BCE – 31 BCE',
                'principal_figures' => ['Julius Caesar', 'Pompey', 'Octavian'],
            ]),
            'created_by' => 'seeder',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $caesarId = $this->findOrCreateEntity('Julius Caesar', 'person');
        $pompeyId = $this->findOrCreateEntity('Pompey', 'person');

        $rel2Id = Str::uuid()->toString();
        DB::table('relationships')->insert([
            'relationship_id' => $rel2Id,
            'source_entity_id' => $caesarId,
            'target_entity_id' => $pompeyId,
            'relationship_type' => 'at_war_with',
            'temporal_start' => '-0049',
            'temporal_end' => '-0045',
            'start_year' => -49,
            'end_year' => -45,
            'created_by' => 'seeder',
            'created_at' => now(),
        ]);

        $entry2aId = Str::uuid()->toString();
        $entry2bId = Str::uuid()->toString();
        DB::table('chronicle_entries')->insert([
            [
                'entry_id' => $entry2aId,
                'chronicle_id' => $romanId,
                'sequence_order' => 0,
                'primary_relationship_id' => $rel2Id,
                'narrative_text' => 'Crossing the Rubicon in 49 BCE, Julius Caesar plunged the Roman Republic into civil war. His rivalry with Pompey the Great defined a decade of bloodshed.',
                'notes' => 'The Rubicon crossing marked the point of no return.',
                'source_evidence' => json_encode(['Appian 2.41']),
                'generated_by' => 'seeder',
                'created_at' => now(),
                'updated_at' => now(),
            ],
            [
                'entry_id' => $entry2bId,
                'chronicle_id' => $romanId,
                'sequence_order' => 1,
                'primary_relationship_id' => null,
                'narrative_text' => 'After Pompey\'s death in 48 BCE, Caesar consolidated power as dictator perpetuo. His assassination in 44 BCE triggered a second round of civil wars, ending only with Octavian\'s victory at Actium in 31 BCE.',
                'notes' => 'The Second Triumvirate (Octavian, Antony, Lepidus) was formed in 43 BCE.',
                'source_evidence' => json_encode(['Appian 2.123']),
                'generated_by' => 'seeder',
                'created_at' => now(),
                'updated_at' => now(),
            ],
        ]);

        // ── Chronicle 3: Fall of Constantinople (1453) ──────────
        $fallId = Str::uuid()->toString();
        DB::table('chronicles')->insert([
            'chronicle_id' => $fallId,
            'title' => 'Fall of Constantinople',
            'slug' => 'fall-of-constantinople',
            'source_type' => 'article',
            'source_reference' => 'Steven Runciman, The Fall of Constantinople 1453',
            'status' => 'published',
            'metadata' => json_encode([
                'year' => 1453,
                'siege_duration_days' => 53,
                'outcome' => 'Ottoman victory, end of Byzantine Empire',
            ]),
            'created_by' => 'seeder',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $constantineId = $this->findOrCreateEntity('Constantine XI', 'person');
        $mehmedId = $this->findOrCreateEntity('Mehmed II', 'person');

        $rel3Id = Str::uuid()->toString();
        DB::table('relationships')->insert([
            'relationship_id' => $rel3Id,
            'source_entity_id' => $mehmedId,
            'target_entity_id' => $constantineId,
            'relationship_type' => 'victorious_at',
            'temporal_start' => '1453-05-29',
            'temporal_end' => '1453-05-29',
            'start_year' => 1453,
            'end_year' => 1453,
            'created_by' => 'seeder',
            'created_at' => now(),
        ]);

        $entry3Id = Str::uuid()->toString();
        DB::table('chronicle_entries')->insert([
            'entry_id' => $entry3Id,
            'chronicle_id' => $fallId,
            'sequence_order' => 0,
            'primary_relationship_id' => $rel3Id,
            'narrative_text' => 'On May 29, 1453, after a 53-day siege, Sultan Mehmed II\'s forces breached the Theodosian Walls of Constantinople. Emperor Constantine XI died defending the city, marking the definitive end of the Byzantine Empire and a pivotal moment in world history.',
            'notes' => 'The Ottomans employed large-scale cannon, including the "Basilica" cannon designed by Orban.',
            'source_evidence' => json_encode(['Runciman 1965, pp. 120–145']),
            'generated_by' => 'seeder',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->command->info('Chronicles seeded: 3 chronicles with '.$this->countEntries($didgoriId).' + '.$this->countEntries($romanId).' + '.$this->countEntries($fallId).' entries.');
    }

    private function findOrCreateEntity(string $name, string $type): string
    {
        $existing = DB::table('entities')->where('name', $name)->first();
        if ($existing) {
            return $existing->entity_id;
        }

        $id = Str::uuid()->toString();

        $entityType = match ($type) {
            'person' => EntityType::Person->value,
            'event' => EntityType::EventBattle->value,
            default => EntityType::PoliticalEntity->value,
        };

        $entityGroup = match ($type) {
            'person' => EntityGroup::Polity->value,
            'event' => EntityGroup::Event->value,
            default => EntityGroup::Polity->value,
        };

        DB::table('entities')->insert([
            'entity_id' => $id,
            'name' => $name,
            'entity_type' => $entityType,
            'entity_group' => $entityGroup,
            'verification_status' => 'pipeline_draft',
            'created_by' => 'seeder',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $id;
    }

    private function countEntries(string $chronicleId): int
    {
        return DB::table('chronicle_entries')->where('chronicle_id', $chronicleId)->count();
    }
}
