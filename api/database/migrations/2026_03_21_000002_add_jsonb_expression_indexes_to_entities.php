<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /**
     * Run the migrations.
     *
     * Adds partial expression indexes on the `attributes` JSONB column for the
     * most common admin-panel filter patterns. Each index is scoped to a single
     * entity_type to keep them narrow and fast.
     *
     * These complement the GIN index on `attributes` (which handles ad-hoc
     * containment queries) by providing fast B-tree equality lookups.
     */
    public function up(): void
    {
        // Political entities
        DB::statement("CREATE INDEX entities_attr_political_subtype_idx
            ON entities ((attributes->>'political_subtype'))
            WHERE entity_type = 'political_entity'");

        DB::statement("CREATE INDEX entities_attr_government_type_idx
            ON entities ((attributes->>'government_type'))
            WHERE entity_type = 'political_entity'");

        // Cities
        DB::statement("CREATE INDEX entities_attr_settlement_subtype_idx
            ON entities ((attributes->>'settlement_subtype'))
            WHERE entity_type = 'city'");

        // Military units
        DB::statement("CREATE INDEX entities_attr_unit_subtype_idx
            ON entities ((attributes->>'unit_subtype'))
            WHERE entity_type = 'military_unit'");

        // Infrastructure
        DB::statement("CREATE INDEX entities_attr_monument_subtype_idx
            ON entities ((attributes->>'monument_subtype'))
            WHERE entity_type = 'infrastructure_monument'");

        // Wars
        DB::statement("CREATE INDEX entities_attr_war_subtype_idx
            ON entities ((attributes->>'war_subtype'))
            WHERE entity_type = 'event_war'");

        // Battles
        DB::statement("CREATE INDEX entities_attr_battle_outcome_idx
            ON entities ((attributes->>'outcome'))
            WHERE entity_type = 'event_battle'");

        // Trade routes
        DB::statement("CREATE INDEX entities_attr_route_subtype_idx
            ON entities ((attributes->>'route_subtype'))
            WHERE entity_type = 'trade_route'");

        // Natural resources
        DB::statement("CREATE INDEX entities_attr_resource_category_idx
            ON entities ((attributes->>'resource_category'))
            WHERE entity_type = 'natural_resource'");

        // Epidemics
        DB::statement("CREATE INDEX entities_attr_epidemic_subtype_idx
            ON entities ((attributes->>'epidemic_subtype'))
            WHERE entity_type = 'epidemic_disease'");

        // Persons
        DB::statement("CREATE INDEX entities_attr_person_gender_idx
            ON entities ((attributes->>'gender'))
            WHERE entity_type = 'person'");
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        DB::statement('DROP INDEX IF EXISTS entities_attr_political_subtype_idx');
        DB::statement('DROP INDEX IF EXISTS entities_attr_government_type_idx');
        DB::statement('DROP INDEX IF EXISTS entities_attr_settlement_subtype_idx');
        DB::statement('DROP INDEX IF EXISTS entities_attr_unit_subtype_idx');
        DB::statement('DROP INDEX IF EXISTS entities_attr_monument_subtype_idx');
        DB::statement('DROP INDEX IF EXISTS entities_attr_war_subtype_idx');
        DB::statement('DROP INDEX IF EXISTS entities_attr_battle_outcome_idx');
        DB::statement('DROP INDEX IF EXISTS entities_attr_route_subtype_idx');
        DB::statement('DROP INDEX IF EXISTS entities_attr_resource_category_idx');
        DB::statement('DROP INDEX IF EXISTS entities_attr_epidemic_subtype_idx');
        DB::statement('DROP INDEX IF EXISTS entities_attr_person_gender_idx');
    }
};
