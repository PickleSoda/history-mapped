<?php

declare(strict_types=1);

namespace App\Http\Requests\Admin\Concerns;

use App\Enums\BattleOutcome;
use App\Enums\BattleSubtype;
use App\Enums\CulturalWorkSubtype;
use App\Enums\CurrencyType;
use App\Enums\DisasterSubtype;
use App\Enums\DiplomaticStatus;
use App\Enums\EntityType;
use App\Enums\EpidemicSeverity;
use App\Enums\EpidemicSubtype;
use App\Enums\ExtractionInfraSubtype;
use App\Enums\Gender;
use App\Enums\GovernmentType;
use App\Enums\IntellectualMovementSubtype;
use App\Enums\LanguageRole;
use App\Enums\LanguageStatus;
use App\Enums\MigrationSubtype;
use App\Enums\MilitaryComposition;
use App\Enums\MilitaryUnitSubtype;
use App\Enums\MonumentSubtype;
use App\Enums\PersonRole;
use App\Enums\PoliticalEntitySubtype;
use App\Enums\RebellionSubtype;
use App\Enums\ReformSubtype;
use App\Enums\ReligiousMovementSubtype;
use App\Enums\ResourceCategory;
use App\Enums\ResourceRenewability;
use App\Enums\SettlementSubtype;
use App\Enums\SocialClassSubtype;
use App\Enums\SuccessionType;
use App\Enums\TechnologyDomain;
use App\Enums\TradeRouteSubtype;
use App\Enums\TreatySubtype;
use App\Enums\WarSubtype;
use Illuminate\Validation\Rule;

/**
 * Provides per-entity-type attribute validation rules for StoreEntityRequest
 * and UpdateEntityRequest.
 *
 * All attribute fields are nullable and use 'sometimes' so partial saves work.
 * Complex nested array fields (population_estimates, commanders, etc.) are
 * accepted as-is via the top-level 'attributes' => ['sometimes','nullable','array'] rule
 * in the parent request and are not individually validated here.
 */
trait ValidatesEntityAttributes
{
    /**
     * Returns the attributes.* validation rules, scoped by entity_type.
     *
     * @return array<string, mixed>
     */
    protected function attributeRules(): array
    {
        $type = $this->input('entity_type');

        return [

            // ── 4.1 Political Entity ─────────────────────────────────────────
            'attributes.political_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::PoliticalEntity->value, [Rule::enum(PoliticalEntitySubtype::class)]),
            ],
            'attributes.government_type' => [
                'sometimes', 'nullable', 'string',
                Rule::when(
                    in_array($type, [EntityType::PoliticalEntity->value, EntityType::Dynasty->value], true),
                    [Rule::enum(GovernmentType::class)],
                ),
            ],
            'attributes.succession_type' => [
                'sometimes', 'nullable', 'string',
                Rule::when(
                    in_array($type, [EntityType::PoliticalEntity->value, EntityType::Dynasty->value], true),
                    [Rule::enum(SuccessionType::class)],
                ),
            ],

            // ── 4.2 Person ───────────────────────────────────────────────────
            'attributes.gender' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::Person->value, [Rule::enum(Gender::class)]),
            ],
            'attributes.birth_date' => [
                'sometimes', 'nullable', 'string', 'max:50',
            ],
            'attributes.death_date' => [
                'sometimes', 'nullable', 'string', 'max:50',
            ],
            'attributes.ethnicity' => [
                'sometimes', 'nullable', 'string', 'max:255',
            ],
            'attributes.cause_of_death' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],

            // ── 4.3 Dynasty ──────────────────────────────────────────────────
            'attributes.founding_event' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.ethnic_origin' => [
                'sometimes', 'nullable', 'string', 'max:255',
            ],
            'attributes.legitimacy_basis' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],

            // ── 4.4 Military Unit ────────────────────────────────────────────
            'attributes.unit_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::MilitaryUnit->value, [Rule::enum(MilitaryUnitSubtype::class)]),
            ],
            'attributes.composition' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::MilitaryUnit->value, [Rule::enum(MilitaryComposition::class)]),
            ],

            // ── 4.5 City ─────────────────────────────────────────────────────
            'attributes.settlement_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::City->value, [Rule::enum(SettlementSubtype::class)]),
            ],
            'attributes.elevation_m' => [
                'sometimes', 'nullable', 'numeric',
            ],
            'attributes.founding_legend' => [
                'sometimes', 'nullable', 'string', 'max:2000',
            ],

            // ── 4.6 Infrastructure / Monument ────────────────────────────────
            'attributes.monument_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::InfrastructureMonument->value, [Rule::enum(MonumentSubtype::class)]),
            ],
            'attributes.construction_start' => [
                'sometimes', 'nullable', 'string', 'max:50',
            ],
            'attributes.construction_end' => [
                'sometimes', 'nullable', 'string', 'max:50',
            ],
            'attributes.current_condition' => [
                'sometimes', 'nullable', 'string',
                Rule::when(
                    $type === EntityType::InfrastructureMonument->value,
                    [Rule::in(['extant', 'ruins', 'destroyed', 'rebuilt', 'submerged'])],
                ),
            ],
            'attributes.destruction_date' => [
                'sometimes', 'nullable', 'string', 'max:50',
            ],
            'attributes.destruction_cause' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.unesco_status' => [
                'sometimes', 'nullable', 'string', 'max:255',
            ],

            // ── 4.7 Religious Movement ───────────────────────────────────────
            'attributes.movement_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::ReligiousMovement->value, [Rule::enum(ReligiousMovementSubtype::class)]),
            ],
            'attributes.core_doctrines' => [
                'sometimes', 'nullable', 'string', 'max:2000',
            ],
            'attributes.institutional_structure' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],

            // ── 4.8 Trade Route ──────────────────────────────────────────────
            'attributes.route_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::TradeRoute->value, [Rule::enum(TradeRouteSubtype::class)]),
            ],

            // ── 4.9 Natural Resource ─────────────────────────────────────────
            'attributes.resource_category' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::NaturalResource->value, [Rule::enum(ResourceCategory::class)]),
            ],
            'attributes.renewability' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::NaturalResource->value, [Rule::enum(ResourceRenewability::class)]),
            ],
            'attributes.is_tradeable' => [
                'sometimes', 'nullable', 'boolean',
            ],
            'attributes.substitutability' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.transport_difficulty' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.cultural_value' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],

            // ── 4.10 Extraction Infrastructure ───────────────────────────────
            'attributes.infra_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::ExtractionInfra->value, [Rule::enum(ExtractionInfraSubtype::class)]),
            ],
            'attributes.scale' => [
                'sometimes', 'nullable', 'string',
                Rule::when(
                    $type === EntityType::ExtractionInfra->value,
                    [Rule::in(['small', 'medium', 'large', 'industrial'])],
                ),
            ],

            // ── 4.11 Currency / Monetary System ──────────────────────────────
            'attributes.currency_type' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::CurrencyMonetarySystem->value, [Rule::enum(CurrencyType::class)]),
            ],

            // ── 4.12 Technology ───────────────────────────────────────────────
            'attributes.tech_domain' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::Technology->value, [Rule::enum(TechnologyDomain::class)]),
            ],
            'attributes.impact_description' => [
                'sometimes', 'nullable', 'string', 'max:2000',
            ],

            // ── 4.13 Educational Institution ─────────────────────────────────
            'attributes.institution_type' => [
                'sometimes', 'nullable', 'string', 'max:100',
            ],
            'attributes.library_holdings' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],

            // ── 4.14 Event — War ─────────────────────────────────────────────
            'attributes.war_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::EventWar->value, [Rule::enum(WarSubtype::class)]),
            ],
            'attributes.casus_belli' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.territorial_changes' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],

            // ── 4.15 Event — Battle ───────────────────────────────────────────
            'attributes.battle_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::EventBattle->value, [Rule::enum(BattleSubtype::class)]),
            ],
            'attributes.outcome' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::EventBattle->value, [Rule::enum(BattleOutcome::class)]),
                Rule::when(
                    $type === EntityType::EventRebellion->value,
                    [Rule::in(['success', 'failure', 'partial', 'ongoing'])],
                ),
            ],
            'attributes.victor_side' => [
                'sometimes', 'nullable', 'string', 'max:50',
            ],
            'attributes.tactical_notes' => [
                'sometimes', 'nullable', 'string', 'max:2000',
            ],

            // ── 4.16 Event — Treaty ───────────────────────────────────────────
            'attributes.treaty_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::EventTreaty->value, [Rule::enum(TreatySubtype::class)]),
            ],
            'attributes.key_provisions' => [
                'sometimes', 'nullable', 'string', 'max:2000',
            ],
            'attributes.duration' => [
                'sometimes', 'nullable', 'string', 'max:255',
            ],
            'attributes.termination_date' => [
                'sometimes', 'nullable', 'string', 'max:50',
            ],
            'attributes.termination_reason' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],

            // ── 4.17 Event — Rebellion ────────────────────────────────────────
            'attributes.rebellion_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::EventRebellion->value, [Rule::enum(RebellionSubtype::class)]),
            ],
            'attributes.government_change' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.repression' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],

            // ── 4.18 Event — Natural Disaster ─────────────────────────────────
            'attributes.disaster_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::EventNaturalDisaster->value, [Rule::enum(DisasterSubtype::class)]),
            ],
            'attributes.economic_damage' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.societal_response' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.long_term_consequences' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],

            // ── 4.19 Event — Technology Adoption ──────────────────────────────
            'attributes.acquisition_method' => [
                'sometimes', 'nullable', 'string',
                Rule::when(
                    $type === EntityType::EventTechAdoption->value,
                    [Rule::in(['independent_invention', 'trade', 'conquest', 'espionage'])],
                ),
            ],
            'attributes.adaptation_notes' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.impact' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.diffusion_speed' => [
                'sometimes', 'nullable', 'string',
                Rule::when(
                    $type === EntityType::EventTechAdoption->value,
                    [Rule::in(['rapid', 'gradual', 'incomplete'])],
                ),
            ],

            // ── 4.20 Event — Legal Reform ─────────────────────────────────────
            'attributes.reform_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::EventLegalReform->value, [Rule::enum(ReformSubtype::class)]),
            ],
            'attributes.provisions' => [
                'sometimes', 'nullable', 'string', 'max:2000',
            ],
            'attributes.motivation' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.longevity' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.effects_intended' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.effects_unintended' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.reversal_date' => [
                'sometimes', 'nullable', 'string', 'max:50',
            ],

            // ── 4.21 Epidemic / Disease ───────────────────────────────────────
            'attributes.epidemic_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::EpidemicDisease->value, [Rule::enum(EpidemicSubtype::class)]),
            ],
            'attributes.severity' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::EpidemicDisease->value, [Rule::enum(EpidemicSeverity::class)]),
            ],
            'attributes.spread_vector' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.societal_responses' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.economic_consequences' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],

            // ── 4.22 Diplomatic Relationship ──────────────────────────────────
            'attributes.diplomatic_status' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::DiplomaticRelationship->value, [Rule::enum(DiplomaticStatus::class)]),
            ],
            'attributes.terms' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.power_asymmetry' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.military_obligations' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.termination_cause' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],

            // ── 4.23 Migration ────────────────────────────────────────────────
            'attributes.migration_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::Migration->value, [Rule::enum(MigrationSubtype::class)]),
            ],
            'attributes.migrating_group' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.voluntary' => [
                'sometimes', 'nullable', 'boolean',
            ],
            'attributes.casualties_during' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.impact_origin' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.impact_destination' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],

            // ── 4.24 Social Class ─────────────────────────────────────────────
            'attributes.class_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::SocialClass->value, [Rule::enum(SocialClassSubtype::class)]),
            ],
            'attributes.economic_role' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.legal_status' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.political_power' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.social_mobility' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.military_obligation' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.education_access' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],

            // ── 4.25 Cultural Work ────────────────────────────────────────────
            'attributes.work_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::CulturalWork->value, [Rule::enum(CulturalWorkSubtype::class)]),
            ],
            'attributes.style_genre' => [
                'sometimes', 'nullable', 'string', 'max:255',
            ],
            'attributes.preservation_status' => [
                'sometimes', 'nullable', 'string',
                Rule::when(
                    $type === EntityType::CulturalWork->value,
                    [Rule::in(['extant', 'fragments', 'lost', 'reconstructed', 'copies_only'])],
                ),
            ],
            'attributes.current_location' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.influence_description' => [
                'sometimes', 'nullable', 'string', 'max:2000',
            ],

            // ── 4.26 Intellectual Movement ────────────────────────────────────
            'attributes.intellectual_movement_subtype' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::IntellectualMovement->value, [Rule::enum(IntellectualMovementSubtype::class)]),
            ],
            'attributes.core_ideas' => [
                'sometimes', 'nullable', 'string', 'max:2000',
            ],
            'attributes.methodology' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.style_characteristics' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],

            // ── 4.27 Archaeological Culture ───────────────────────────────────
            'attributes.technology_level' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.economic_base' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.settlement_patterns' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.burial_practices' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.hypothesized_ethnicity' => [
                'sometimes', 'nullable', 'string', 'max:255',
            ],
            'attributes.evidence_quality' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],

            // ── 4.28 Language ─────────────────────────────────────────────────
            'attributes.language_family' => [
                'sometimes', 'nullable', 'string', 'max:255',
            ],
            'attributes.language_status' => [
                'sometimes', 'nullable', 'string',
                Rule::when($type === EntityType::Language->value, [Rule::enum(LanguageStatus::class)]),
            ],
            'attributes.writing_system' => [
                'sometimes', 'nullable', 'string', 'max:255',
            ],
            'attributes.iso_639_code' => [
                'sometimes', 'nullable', 'string', 'max:10',
            ],

            // ── 4.29 Religious Text ───────────────────────────────────────────
            'attributes.text_type' => [
                'sometimes', 'nullable', 'string',
                Rule::when(
                    $type === EntityType::ReligiousText->value,
                    [Rule::in(['scripture', 'commentary', 'relic', 'artifact'])],
                ),
            ],
            'attributes.composition_date' => [
                'sometimes', 'nullable', 'string', 'max:50',
            ],
            'attributes.genre' => [
                'sometimes', 'nullable', 'string',
                Rule::when(
                    $type === EntityType::ReligiousText->value,
                    [Rule::in(['mythology', 'law', 'prophecy', 'wisdom', 'history'])],
                ),
            ],
            'attributes.material' => [
                'sometimes', 'nullable', 'string', 'max:255',
            ],

            // ── 4.30 Legal Code ───────────────────────────────────────────────
            'attributes.promulgation_date' => [
                'sometimes', 'nullable', 'string', 'max:50',
            ],
            'attributes.legal_philosophy' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
            'attributes.enforcement_duration' => [
                'sometimes', 'nullable', 'string', 'max:500',
            ],
            'attributes.modern_significance' => [
                'sometimes', 'nullable', 'string', 'max:1000',
            ],
        ];
    }
}
