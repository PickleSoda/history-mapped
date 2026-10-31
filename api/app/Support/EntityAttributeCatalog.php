<?php

declare(strict_types=1);

namespace App\Support;

use App\Enums\BattleOutcome;
use App\Enums\BattleSubtype;
use App\Enums\CulturalWorkSubtype;
use App\Enums\CurrencyType;
use App\Enums\DiplomaticStatus;
use App\Enums\DisasterSubtype;
use App\Enums\EntityType;
use App\Enums\EpidemicSeverity;
use App\Enums\EpidemicSubtype;
use App\Enums\ExtractionInfraSubtype;
use App\Enums\Gender;
use App\Enums\GovernmentType;
use App\Enums\IntellectualMovementSubtype;
use App\Enums\LanguageStatus;
use App\Enums\MigrationSubtype;
use App\Enums\MilitaryComposition;
use App\Enums\MilitaryUnitSubtype;
use App\Enums\MonumentSubtype;
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

/**
 * The type-specific `attributes` an editor can set on each entity type — the
 * same fields the admin entity form shows per type (its *Section components),
 * with each choice list taken from the enum its validation rule uses
 * (ValidatesEntityAttributes). The AI editor reads this to know which fields
 * exist, and validates its writes against it.
 *
 * Kinds: `choice` (one of `values`), `number`, `boolean`, `text`, `long_text`.
 * `is_tradeable` and `voluntary` are spec booleans the form has no input for.
 */
final class EntityAttributeCatalog
{
    /**
     * Per entity type: attribute key => label + either an enum, a fixed value
     * list, or a kind, plus an optional max length and an example hint.
     *
     * @var array<string, array<string, array{label: string, enum?: class-string<\BackedEnum>, values?: list<string>, kind?: string, max?: int, hint?: string}>>
     */
    private const FIELDS = [
        'political_entity' => [
            'political_subtype' => ['label' => 'Political Subtype', 'enum' => PoliticalEntitySubtype::class],
            'government_type' => ['label' => 'Government Type', 'enum' => GovernmentType::class],
            'succession_type' => ['label' => 'Succession Type', 'enum' => SuccessionType::class],
        ],
        'dynasty' => [
            'government_type' => ['label' => 'Government Type', 'enum' => GovernmentType::class],
            'succession_type' => ['label' => 'Succession Type', 'enum' => SuccessionType::class],
            'founding_event' => ['label' => 'Founding Event', 'kind' => 'text', 'max' => 500, 'hint' => 'Brief description of founding'],
            'ethnic_origin' => ['label' => 'Ethnic Origin', 'kind' => 'text', 'max' => 255, 'hint' => 'e.g. Frankish'],
            'legitimacy_basis' => ['label' => 'Legitimacy Basis', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. divine right, hereditary'],
        ],
        'person' => [
            'gender' => ['label' => 'Gender', 'enum' => Gender::class],
            'birth_date' => ['label' => 'Birth Date (EDTF)', 'kind' => 'text', 'max' => 50, 'hint' => 'e.g. -356 or 1452'],
            'death_date' => ['label' => 'Death Date (EDTF)', 'kind' => 'text', 'max' => 50, 'hint' => 'e.g. -323 or 1519'],
            'ethnicity' => ['label' => 'Ethnicity', 'kind' => 'text', 'max' => 255, 'hint' => 'e.g. Macedonian'],
            'cause_of_death' => ['label' => 'Cause of Death', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. fever, assassination'],
        ],
        'military_unit' => [
            'unit_subtype' => ['label' => 'Unit Subtype', 'enum' => MilitaryUnitSubtype::class],
            'composition' => ['label' => 'Composition', 'enum' => MilitaryComposition::class],
        ],
        'diplomatic_relationship' => [
            'diplomatic_status' => ['label' => 'Diplomatic Status', 'enum' => DiplomaticStatus::class],
            'terms' => ['label' => 'Terms', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Key terms of the relationship'],
            'power_asymmetry' => ['label' => 'Power Asymmetry', 'kind' => 'text', 'max' => 500, 'hint' => 'Description of power imbalance'],
            'military_obligations' => ['label' => 'Military Obligations', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. mutual defense'],
            'termination_cause' => ['label' => 'Termination Cause', 'kind' => 'text', 'max' => 500, 'hint' => 'How/why did it end?'],
        ],
        'social_class' => [
            'class_subtype' => ['label' => 'Class Subtype', 'enum' => SocialClassSubtype::class],
            'economic_role' => ['label' => 'Economic Role', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. tax farmers, landowners'],
            'legal_status' => ['label' => 'Legal Status', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. freemen, slaves'],
            'political_power' => ['label' => 'Political Power', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. voting rights, senate access'],
            'social_mobility' => ['label' => 'Social Mobility', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. low / high'],
            'military_obligation' => ['label' => 'Military Obligation', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. mandatory service'],
            'education_access' => ['label' => 'Education Access', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. restricted to clergy'],
        ],
        'city' => [
            'settlement_subtype' => ['label' => 'Settlement Subtype', 'enum' => SettlementSubtype::class],
            'elevation_m' => ['label' => 'Elevation (m)', 'kind' => 'number', 'hint' => 'e.g. 21'],
            'founding_legend' => ['label' => 'Founding Legend', 'kind' => 'long_text', 'max' => 2000, 'hint' => 'Brief founding story or myth'],
        ],
        'infrastructure_monument' => [
            'monument_subtype' => ['label' => 'Monument Subtype', 'enum' => MonumentSubtype::class],
            'construction_start' => ['label' => 'Construction Start (EDTF)', 'kind' => 'text', 'max' => 50, 'hint' => 'e.g. -447'],
            'construction_end' => ['label' => 'Construction End (EDTF)', 'kind' => 'text', 'max' => 50, 'hint' => 'e.g. -432'],
            'current_condition' => ['label' => 'Current Condition', 'values' => ['extant', 'ruins', 'destroyed', 'rebuilt', 'submerged']],
            'destruction_date' => ['label' => 'Destruction Date (EDTF)', 'kind' => 'text', 'max' => 50, 'hint' => 'e.g. 80 or 1453'],
            'destruction_cause' => ['label' => 'Destruction Cause', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. fire, earthquake, sack'],
            'unesco_status' => ['label' => 'UNESCO Status', 'kind' => 'text', 'max' => 255, 'hint' => 'e.g. World Heritage Site'],
        ],
        'extraction_infra' => [
            'infra_subtype' => ['label' => 'Infrastructure Subtype', 'enum' => ExtractionInfraSubtype::class],
            'scale' => ['label' => 'Scale', 'values' => ['small', 'medium', 'large', 'industrial']],
        ],
        'educational_institution' => [
            'institution_type' => ['label' => 'Institution Type', 'kind' => 'text', 'max' => 100, 'hint' => 'e.g. academy, university, library, madrasa'],
            'library_holdings' => ['label' => 'Library Holdings', 'kind' => 'text', 'max' => 500, 'hint' => 'Description of holdings'],
        ],
        'event_war' => [
            'war_subtype' => ['label' => 'War Subtype', 'enum' => WarSubtype::class],
            'casus_belli' => ['label' => 'Casus Belli', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Stated or real reason for war'],
            'territorial_changes' => ['label' => 'Territorial Changes', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Summary of territory gained or lost'],
        ],
        'event_battle' => [
            'battle_subtype' => ['label' => 'Battle Subtype', 'enum' => BattleSubtype::class],
            'outcome' => ['label' => 'Outcome', 'enum' => BattleOutcome::class],
            'victor_side' => ['label' => 'Victor Side', 'kind' => 'text', 'max' => 50, 'hint' => 'e.g. side_a or name'],
            'tactical_notes' => ['label' => 'Tactical Notes', 'kind' => 'long_text', 'max' => 2000, 'hint' => 'Key tactical details'],
        ],
        'event_treaty' => [
            'treaty_subtype' => ['label' => 'Treaty Subtype', 'enum' => TreatySubtype::class],
            'key_provisions' => ['label' => 'Key Provisions', 'kind' => 'long_text', 'max' => 2000, 'hint' => 'Main terms of the agreement'],
            'duration' => ['label' => 'Duration', 'kind' => 'text', 'max' => 255, 'hint' => 'e.g. 50 years, perpetual'],
            'termination_date' => ['label' => 'Termination Date (EDTF)', 'kind' => 'text', 'max' => 50, 'hint' => 'e.g. 200'],
            'termination_reason' => ['label' => 'Termination Reason', 'kind' => 'text', 'max' => 500, 'hint' => 'Why the treaty ended'],
        ],
        'event_rebellion' => [
            'rebellion_subtype' => ['label' => 'Rebellion Subtype', 'enum' => RebellionSubtype::class],
            'outcome' => ['label' => 'Outcome', 'values' => ['success', 'failure', 'partial', 'ongoing']],
            'government_change' => ['label' => 'Government Change', 'kind' => 'text', 'max' => 500, 'hint' => 'What changed after the rebellion'],
            'repression' => ['label' => 'Repression', 'kind' => 'text', 'max' => 500, 'hint' => 'How was the rebellion suppressed?'],
        ],
        'event_natural_disaster' => [
            'disaster_subtype' => ['label' => 'Disaster Subtype', 'enum' => DisasterSubtype::class],
            'economic_damage' => ['label' => 'Economic Damage', 'kind' => 'text', 'max' => 500, 'hint' => 'Description of economic damage'],
            'societal_response' => ['label' => 'Societal Response', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'How did society respond?'],
            'long_term_consequences' => ['label' => 'Long-term Consequences', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Lasting historical effects'],
        ],
        'event_tech_adoption' => [
            'acquisition_method' => ['label' => 'Acquisition Method', 'values' => ['independent_invention', 'trade', 'conquest', 'espionage'], 'hint' => 'How was it acquired?'],
            'diffusion_speed' => ['label' => 'Diffusion Speed', 'values' => ['rapid', 'gradual', 'incomplete'], 'hint' => 'How quickly did it spread?'],
            'adaptation_notes' => ['label' => 'Adaptation Notes', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Local adaptations or modifications'],
            'impact' => ['label' => 'Impact', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Historical impact of the adoption'],
        ],
        'event_legal_reform' => [
            'reform_subtype' => ['label' => 'Reform Subtype', 'enum' => ReformSubtype::class],
            'provisions' => ['label' => 'Provisions', 'kind' => 'long_text', 'max' => 2000, 'hint' => 'Main provisions of the reform'],
            'motivation' => ['label' => 'Motivation', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Political or social motivation'],
            'longevity' => ['label' => 'Longevity', 'kind' => 'text', 'max' => 500, 'hint' => 'How long did it last?'],
            'effects_intended' => ['label' => 'Intended Effects', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Planned outcomes'],
            'effects_unintended' => ['label' => 'Unintended Effects', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Unexpected consequences'],
            'reversal_date' => ['label' => 'Reversal Date (EDTF)', 'kind' => 'text', 'max' => 50, 'hint' => 'When was it reversed?'],
        ],
        'epidemic_disease' => [
            'epidemic_subtype' => ['label' => 'Epidemic Subtype', 'enum' => EpidemicSubtype::class],
            'severity' => ['label' => 'Severity', 'enum' => EpidemicSeverity::class],
            'spread_vector' => ['label' => 'Spread Vector', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. fleas/rats, water, airborne'],
            'societal_responses' => ['label' => 'Societal Responses', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'How did society respond?'],
            'economic_consequences' => ['label' => 'Economic Consequences', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Economic effects of the epidemic'],
        ],
        'migration' => [
            'voluntary' => ['label' => 'Voluntary', 'kind' => 'boolean'],
            'migration_subtype' => ['label' => 'Migration Subtype', 'enum' => MigrationSubtype::class],
            'migrating_group' => ['label' => 'Migrating Group', 'kind' => 'text', 'max' => 500, 'hint' => 'Name of the migrating people'],
            'casualties_during' => ['label' => 'Casualties During Migration', 'kind' => 'text', 'max' => 500, 'hint' => 'Description of casualties'],
            'impact_origin' => ['label' => 'Impact on Origin Region', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Effects on the region of origin'],
            'impact_destination' => ['label' => 'Impact on Destination Region', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Effects on the destination region'],
        ],
        'trade_route' => [
            'route_subtype' => ['label' => 'Route Subtype', 'enum' => TradeRouteSubtype::class],
        ],
        'natural_resource' => [
            'is_tradeable' => ['label' => 'Tradeable', 'kind' => 'boolean'],
            'resource_category' => ['label' => 'Resource Category', 'enum' => ResourceCategory::class],
            'renewability' => ['label' => 'Renewability', 'enum' => ResourceRenewability::class],
            'substitutability' => ['label' => 'Substitutability', 'kind' => 'text', 'max' => 500, 'hint' => 'Can it be substituted? How?'],
            'transport_difficulty' => ['label' => 'Transport Difficulty', 'kind' => 'text', 'max' => 500, 'hint' => 'Description of transport challenges'],
            'cultural_value' => ['label' => 'Cultural Value', 'kind' => 'text', 'max' => 500, 'hint' => 'Ritual or prestige significance'],
        ],
        'currency_monetary_system' => [
            'currency_type' => ['label' => 'Currency Type', 'enum' => CurrencyType::class],
        ],
        'cultural_work' => [
            'work_subtype' => ['label' => 'Work Subtype', 'enum' => CulturalWorkSubtype::class],
            'style_genre' => ['label' => 'Style / Genre', 'kind' => 'text', 'max' => 255, 'hint' => 'e.g. epic poetry, naturalist sculpture'],
            'preservation_status' => ['label' => 'Preservation Status', 'values' => ['extant', 'fragments', 'lost', 'reconstructed', 'copies_only']],
            'current_location' => ['label' => 'Current Location', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. British Museum, London'],
            'influence_description' => ['label' => 'Influence Description', 'kind' => 'long_text', 'max' => 2000, 'hint' => 'How did this work influence later culture?'],
        ],
        'intellectual_movement' => [
            'intellectual_movement_subtype' => ['label' => 'Movement Subtype', 'enum' => IntellectualMovementSubtype::class],
            'core_ideas' => ['label' => 'Core Ideas', 'kind' => 'long_text', 'max' => 2000, 'hint' => 'Central tenets or principles'],
            'methodology' => ['label' => 'Methodology', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Approach or method used'],
            'style_characteristics' => ['label' => 'Style Characteristics', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Defining aesthetic or stylistic features'],
        ],
        'archaeological_culture' => [
            'technology_level' => ['label' => 'Technology Level', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. Bronze Age, Neolithic'],
            'economic_base' => ['label' => 'Economic Base', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. pastoralism, agriculture, trade'],
            'settlement_patterns' => ['label' => 'Settlement Patterns', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. dispersed farmsteads, hillforts'],
            'burial_practices' => ['label' => 'Burial Practices', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. inhumation, cremation, kurgan'],
            'hypothesized_ethnicity' => ['label' => 'Hypothesized Ethnicity', 'kind' => 'text', 'max' => 255, 'hint' => 'Modern scholarly attribution'],
            'evidence_quality' => ['label' => 'Evidence Quality', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. well-documented, sparse'],
        ],
        'language' => [
            'language_status' => ['label' => 'Language Status', 'enum' => LanguageStatus::class],
            'language_family' => ['label' => 'Language Family', 'kind' => 'text', 'max' => 255, 'hint' => 'e.g. Indo-European, Semitic'],
            'writing_system' => ['label' => 'Writing System', 'kind' => 'text', 'max' => 255, 'hint' => 'e.g. cuneiform, Latin alphabet'],
            'iso_639_code' => ['label' => 'ISO 639 Code', 'kind' => 'text', 'max' => 10, 'hint' => 'e.g. lat, grc'],
        ],
        'religious_text' => [
            'text_type' => ['label' => 'Text Type', 'values' => ['scripture', 'commentary', 'relic', 'artifact']],
            'genre' => ['label' => 'Genre', 'values' => ['mythology', 'law', 'prophecy', 'wisdom', 'history']],
            'composition_date' => ['label' => 'Composition Date (EDTF)', 'kind' => 'text', 'max' => 50, 'hint' => 'e.g. -600'],
            'material' => ['label' => 'Material', 'kind' => 'text', 'max' => 255, 'hint' => 'e.g. papyrus, parchment, stone'],
        ],
        'legal_code' => [
            'promulgation_date' => ['label' => 'Promulgation Date (EDTF)', 'kind' => 'text', 'max' => 50, 'hint' => 'e.g. -450'],
            'key_provisions' => ['label' => 'Key Provisions', 'kind' => 'long_text', 'max' => 2000, 'hint' => 'Main provisions of the code'],
            'legal_philosophy' => ['label' => 'Legal Philosophy', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Underlying legal principles'],
            'enforcement_duration' => ['label' => 'Enforcement Duration', 'kind' => 'text', 'max' => 500, 'hint' => 'How long was it in force?'],
            'modern_significance' => ['label' => 'Modern Significance', 'kind' => 'long_text', 'max' => 1000, 'hint' => 'Influence on modern legal systems'],
        ],
        'religious_movement' => [
            'movement_subtype' => ['label' => 'Movement Subtype', 'enum' => ReligiousMovementSubtype::class],
            'core_doctrines' => ['label' => 'Core Doctrines', 'kind' => 'long_text', 'max' => 2000, 'hint' => 'Central beliefs and teachings'],
            'institutional_structure' => ['label' => 'Institutional Structure', 'kind' => 'text', 'max' => 500, 'hint' => 'e.g. church, temple network, decentralized'],
        ],
        'technology' => [
            'tech_domain' => ['label' => 'Technology Domain', 'enum' => TechnologyDomain::class],
            'impact_description' => ['label' => 'Impact Description', 'kind' => 'long_text', 'max' => 2000, 'hint' => 'Historical significance of this technology'],
        ],
    ];

    /**
     * The attribute fields of one entity type, described for an editor: label,
     * kind, the allowed values of a choice, max length and an example hint.
     *
     * @return array<string, array{label: string, kind: string, values?: list<string>, max?: int, hint?: string}>
     */
    public static function fieldsFor(EntityType|string $type): array
    {
        $key = $type instanceof EntityType ? $type->value : $type;

        return array_map(self::describe(...), self::FIELDS[$key] ?? []);
    }

    /**
     * Every attribute key some type uses.
     *
     * @return list<string>
     */
    public static function allKeys(): array
    {
        return array_values(array_unique(array_merge(...array_values(array_map(array_keys(...), self::FIELDS)))));
    }

    /**
     * Why `$value` can't be stored as `$key` on an entity of `$type`, or null
     * when it can. Null clears a field, so it is always allowed for a known key.
     */
    public static function problem(EntityType|string $type, string $key, mixed $value): ?string
    {
        $typeKey = $type instanceof EntityType ? $type->value : $type;
        $field = self::fieldsFor($typeKey)[$key] ?? null;

        if ($field === null) {
            $known = array_keys(self::FIELDS[$typeKey] ?? []);

            return "'{$key}' is not an attribute of {$typeKey}".($known === [] ? ' (it has none)' : '; use one of: '.implode(', ', $known));
        }

        if ($value === null) {
            return null;
        }

        return match ($field['kind']) {
            'choice' => in_array($value, $field['values'], true)
                ? null
                : "'{$key}' must be one of: ".implode(', ', $field['values']),
            'number' => is_int($value) || is_float($value) || (is_string($value) && is_numeric($value))
                ? null
                : "'{$key}' must be a number",
            'boolean' => is_bool($value) ? null : "'{$key}' must be true or false",
            default => ! is_string($value)
                ? "'{$key}' must be text"
                : (isset($field['max']) && mb_strlen($value) > $field['max'] ? "'{$key}' is longer than {$field['max']} characters" : null),
        };
    }

    /**
     * @param  array{label: string, enum?: class-string<\BackedEnum>, values?: list<string>, kind?: string, max?: int, hint?: string}  $field
     * @return array{label: string, kind: string, values?: list<string>, max?: int, hint?: string}
     */
    private static function describe(array $field): array
    {
        $values = isset($field['enum'])
            ? array_column($field['enum']::cases(), 'value')
            : ($field['values'] ?? null);

        return array_filter([
            'label' => $field['label'],
            'kind' => $values !== null ? 'choice' : ($field['kind'] ?? 'text'),
            'values' => $values,
            'max' => $field['max'] ?? null,
            'hint' => $field['hint'] ?? null,
        ], fn ($v) => $v !== null);
    }
}
