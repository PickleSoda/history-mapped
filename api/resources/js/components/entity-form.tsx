import InputError from '@/components/input-error';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import type { EntityFormOptions, EntityGroup, EntityType } from '@/types';

// ─── Attribute sub-type enums (kept client-side — no backend roundtrip needed) ───

const POLITICAL_ENTITY_SUBTYPES = [
    'empire',
    'kingdom',
    'republic',
    'city_state',
    'tribal_confederation',
    'theocracy',
    'principality',
    'duchy',
    'khanate',
    'sultanate',
    'caliphate',
    'shogunate',
    'confederation',
    'league',
    'colonial_territory',
    'protectorate',
    'vassal_state',
    'free_city',
    'nomadic_polity',
    'other',
] as const;

const GOVERNMENT_TYPES = [
    'absolute_monarchy',
    'constitutional_monarchy',
    'elective_monarchy',
    'oligarchy',
    'aristocratic_republic',
    'democratic_republic',
    'theocracy',
    'military_dictatorship',
    'tribal_chieftainship',
    'feudal',
    'bureaucratic_centralized',
    'colonial_administration',
    'communist_state',
    'fascist_state',
    'anarchy',
    'diarchy',
    'federal',
    'confederal',
    'other',
] as const;

const SUCCESSION_TYPES = [
    'primogeniture',
    'ultimogeniture',
    'elective',
    'tanistry',
    'agnatic',
    'cognatic',
    'appointed',
    'meritocratic',
    'military_acclamation',
    'divine_selection',
    'rotation',
    'other',
    'unknown',
] as const;

const GENDERS = ['male', 'female', 'other', 'unknown'] as const;

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const PERSON_ROLES = [
    'ruler',
    'regent',
    'heir',
    'consort',
    'general',
    'admiral',
    'diplomat',
    'governor',
    'religious_leader',
    'prophet',
    'philosopher',
    'scientist',
    'artist',
    'architect',
    'poet',
    'historian',
    'lawgiver',
    'rebel_leader',
    'merchant',
    'explorer',
    'spy',
    'slave',
    'other',
] as const;

const MILITARY_UNIT_SUBTYPES = [
    'infantry',
    'cavalry',
    'navy',
    'archer_ranged',
    'siege',
    'chariot',
    'elephant_corps',
    'garrison',
    'mercenary_company',
    'legion',
    'phalanx',
    'warband',
    'fleet',
    'air_force',
    'special_forces',
    'militia',
    'guard',
    'other',
] as const;

const MILITARY_COMPOSITIONS = [
    'professional',
    'conscript',
    'mercenary',
    'tribal_warrior',
    'slave_soldier',
    'feudal_levy',
    'volunteer',
    'mixed',
    'unknown',
] as const;

const SETTLEMENT_SUBTYPES = [
    'capital_city',
    'major_city',
    'minor_city',
    'town',
    'village',
    'fortress',
    'port',
    'religious_center',
    'trade_hub',
    'administrative_center',
    'mining_town',
    'oasis',
    'colony',
    'garrison_town',
    'abandoned',
    'other',
] as const;

const MONUMENT_SUBTYPES = [
    'palace',
    'forum',
    'amphitheater',
    'theater',
    'bath_complex',
    'library',
    'market_agora',
    'government_building',
    'temple',
    'cathedral',
    'mosque',
    'monastery',
    'shrine',
    'pyramid',
    'megalithic_structure',
    'sacred_grove',
    'fortification',
    'wall',
    'castle',
    'citadel',
    'watchtower',
    'aqueduct',
    'canal',
    'bridge',
    'road_section',
    'harbor',
    'lighthouse',
    'dam',
    'granary',
    'sewer_system',
    'triumphal_arch',
    'obelisk',
    'mausoleum',
    'tomb',
    'statue',
    'memorial',
    'stele',
    'other',
] as const;

const MONUMENT_CONDITIONS = [
    'extant',
    'ruins',
    'destroyed',
    'rebuilt',
    'submerged',
] as const;

const RELIGIOUS_MOVEMENT_SUBTYPES = [
    'monotheism',
    'polytheism',
    'animism',
    'ancestor_worship',
    'philosophical_religion',
    'mystery_cult',
    'syncretic',
    'sect_denomination',
    'heretical_movement',
    'reform_movement',
    'missionary_movement',
    'monastic_order',
    'other',
] as const;

const TRADE_ROUTE_SUBTYPES = [
    'overland',
    'maritime',
    'riverine',
    'mixed',
    'pilgrimage',
    'military_supply',
    'other',
] as const;

const RESOURCE_CATEGORIES = [
    'grain',
    'livestock',
    'cash_crop',
    'timber',
    'metal_precious',
    'metal_strategic',
    'metal_base',
    'stone_building',
    'gemstone',
    'salt',
    'spice',
    'textile_raw',
    'dye',
    'incense_perfume',
    'fuel',
    'water',
    'fish_seafood',
    'animal_strategic',
    'animal_luxury',
    'medicinal',
    'other',
] as const;

const RESOURCE_RENEWABILITIES = [
    'renewable',
    'finite',
    'cyclical',
    'unknown',
] as const;

const EXTRACTION_INFRA_SUBTYPES = [
    'mine',
    'quarry',
    'farm',
    'plantation',
    'ranch',
    'fishery',
    'forest_logging',
    'hunting_ground',
    'well_spring',
    'salt_works',
    'workshop',
    'shipyard',
    'smithy_foundry',
    'irrigation_system',
    'mill',
    'vineyard',
    'kiln',
    'other',
] as const;

const EXTRACTION_SCALES = ['small', 'medium', 'large', 'industrial'] as const;

const CURRENCY_TYPES = [
    'coin_metal',
    'paper',
    'commodity_money',
    'shell_bead',
    'barter_system',
    'credit_system',
    'other',
] as const;

const TECHNOLOGY_DOMAINS = [
    'military',
    'agricultural',
    'industrial',
    'construction',
    'navigation',
    'communication',
    'medical',
    'metallurgical',
    'textile',
    'writing_printing',
    'astronomical',
    'hydraulic',
    'transportation',
    'food_preservation',
    'other',
] as const;

const WAR_SUBTYPES = [
    'interstate_war',
    'civil_war',
    'colonial_war',
    'religious_war',
    'succession_war',
    'trade_war',
    'border_conflict',
    'raid_series',
    'invasion',
    'siege_campaign',
    'naval_war',
    'tribal_war',
    'other',
] as const;

const BATTLE_SUBTYPES = [
    'pitched_battle',
    'siege',
    'naval_battle',
    'ambush',
    'skirmish',
    'raid',
    'last_stand',
    'other',
] as const;

const BATTLE_OUTCOMES = [
    'decisive_victory',
    'tactical_victory',
    'pyrrhic_victory',
    'draw',
    'tactical_defeat',
    'decisive_defeat',
    'inconclusive',
    'unknown',
] as const;

const TREATY_SUBTYPES = [
    'peace_treaty',
    'alliance_treaty',
    'trade_agreement',
    'marriage_alliance',
    'tribute_agreement',
    'border_demarcation',
    'non_aggression_pact',
    'surrender',
    'ceasefire',
    'mutual_defense',
    'vassalage_agreement',
    'other',
] as const;

const REBELLION_SUBTYPES = [
    'revolution',
    'rebellion',
    'coup',
    'civil_war',
    'peasant_uprising',
    'slave_revolt',
    'military_mutiny',
    'separatist_movement',
    'religious_uprising',
    'other',
] as const;

const REBELLION_OUTCOMES = [
    'success',
    'failure',
    'partial',
    'ongoing',
] as const;

const DISASTER_SUBTYPES = [
    'earthquake',
    'volcanic_eruption',
    'flood',
    'tsunami',
    'drought',
    'famine',
    'wildfire',
    'hurricane_typhoon',
    'landslide',
    'climate_shift',
    'other',
] as const;

const TECH_ADOPTION_METHODS = [
    'independent_invention',
    'trade',
    'conquest',
    'espionage',
] as const;

const DIFFUSION_SPEEDS = ['rapid', 'gradual', 'incomplete'] as const;

const REFORM_SUBTYPES = [
    'legal_code',
    'constitutional_change',
    'administrative_reorganization',
    'land_reform',
    'taxation_reform',
    'military_reform',
    'religious_reform',
    'educational_reform',
    'economic_reform',
    'abolition',
    'enfranchisement',
    'other',
] as const;

const EPIDEMIC_SUBTYPES = [
    'plague_bacterial',
    'plague_viral',
    'smallpox',
    'cholera',
    'malaria',
    'typhus',
    'influenza',
    'tuberculosis',
    'leprosy',
    'dysentery',
    'measles',
    'unknown_pestilence',
    'other',
] as const;

const EPIDEMIC_SEVERITIES = [
    'local',
    'regional',
    'pandemic',
    'unknown',
] as const;

const DIPLOMATIC_STATUSES = [
    'alliance',
    'defensive_pact',
    'trade_agreement',
    'vassalage',
    'tributary',
    'protectorate',
    'personal_union',
    'federation_member',
    'non_aggression',
    'neutrality',
    'war',
    'cold_war',
    'embargo',
    'occupation',
    'other',
] as const;

const MIGRATION_SUBTYPES = [
    'invasion',
    'colonization',
    'forced_deportation',
    'refugee_flight',
    'economic_migration',
    'nomadic_movement',
    'pilgrimage_settlement',
    'slave_trade',
    'diaspora',
    'other',
] as const;

const SOCIAL_CLASS_SUBTYPES = [
    'royalty',
    'nobility',
    'clergy',
    'warrior_class',
    'merchant_class',
    'artisan_class',
    'peasantry',
    'serf',
    'slave',
    'freedman',
    'bureaucrat_literati',
    'nomad_pastoral',
    'outcast_untouchable',
    'intelligentsia',
    'bourgeoisie',
    'proletariat',
    'other',
] as const;

const CULTURAL_WORK_SUBTYPES = [
    'literary_text',
    'philosophical_text',
    'historical_text',
    'religious_text',
    'scientific_text',
    'legal_text',
    'building_architecture',
    'sculpture',
    'painting_mural',
    'mosaic',
    'pottery_ceramics',
    'textile',
    'metalwork',
    'musical_composition',
    'inscription',
    'coin_design',
    'map_cartography',
    'other',
] as const;

const PRESERVATION_STATUSES = [
    'extant',
    'fragments',
    'lost',
    'reconstructed',
    'copies_only',
] as const;

const INTELLECTUAL_MOVEMENT_SUBTYPES = [
    'philosophical_school',
    'artistic_style',
    'literary_movement',
    'scientific_paradigm',
    'legal_tradition',
    'educational_tradition',
    'historiographical',
    'other',
] as const;

const LANGUAGE_STATUSES = [
    'living',
    'extinct',
    'liturgical_only',
    'reconstructed',
    'endangered',
    'revived',
    'unknown',
] as const;

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const LANGUAGE_ROLES = [
    'vernacular',
    'lingua_franca',
    'administrative',
    'liturgical',
    'literary',
    'trade_language',
    'court_language',
    'scholarly',
    'other',
] as const;

const RELIGIOUS_TEXT_TYPES = [
    'scripture',
    'commentary',
    'relic',
    'artifact',
] as const;

const RELIGIOUS_TEXT_GENRES = [
    'mythology',
    'law',
    'prophecy',
    'wisdom',
    'history',
] as const;

// ─── Form data shape ──────────────────────────────────────────────────────────

export type EntityFormData = {
    name: string;
    entity_type: string;
    entity_group: string;
    summary: string;
    significance: string;
    temporal_start: string;
    temporal_end: string;
    date_raw: string;
    date_method: string;
    date_confidence: string;
    duration_type: string;
    location_name: string;
    location_confidence: string;
    location_method: string;
    impact_score: string;
    wikidata_id: string;
    tags: string;
    alternative_names: string;
    verification_status: string;
    confidence: string;
    confidence_notes: string;
    display_priority: string;
    icon_class: string;
    entity_color: string;
    parent_entity_id: string;
    successor_entity_id: string;
    /** Type-specific attribute fields, prefixed with "attr_" */
    [key: `attr_${string}`]: string;
};

export function defaultFormData(): EntityFormData {
    return {
        name: '',
        entity_type: '',
        entity_group: '',
        summary: '',
        significance: '',
        temporal_start: '',
        temporal_end: '',
        date_raw: '',
        date_method: '',
        date_confidence: '',
        duration_type: '',
        location_name: '',
        location_confidence: '',
        location_method: '',
        impact_score: '',
        wikidata_id: '',
        tags: '',
        alternative_names: '',
        verification_status: 'pipeline_draft',
        confidence: '',
        confidence_notes: '',
        display_priority: '',
        icon_class: '',
        entity_color: '',
        parent_entity_id: '',
        successor_entity_id: '',
    };
}

// ─── Props ────────────────────────────────────────────────────────────────────

type Props = {
    data: EntityFormData;
    errors: Partial<Record<string, string>>;
    processing: boolean;
    options: EntityFormOptions;
    onChange: <K extends keyof EntityFormData>(
        field: K,
        value: EntityFormData[K],
    ) => void;
    onSubmit: (e: React.FormEvent) => void;
    submitLabel?: string;
    onCancel?: () => void;
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function labelFromValue(value: string): string {
    return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function FieldWrapper({
    label,
    htmlFor,
    error,
    children,
}: {
    label: string;
    htmlFor: string;
    error?: string;
    children: React.ReactNode;
}) {
    return (
        <div className="grid gap-1.5">
            <Label htmlFor={htmlFor}>{label}</Label>
            {children}
            {error && <InputError message={error} />}
        </div>
    );
}

function EnumSelect({
    id,
    value,
    onChange,
    options,
    placeholder,
}: {
    id: string;
    value: string;
    onChange: (v: string) => void;
    options: readonly string[] | { value: string; label: string }[];
    placeholder: string;
}) {
    const normalised: { value: string; label: string }[] = (
        options as (string | { value: string; label: string })[]
    ).map((o) =>
        typeof o === 'string' ? { value: o, label: labelFromValue(o) } : o,
    );

    return (
        <Select value={value || ''} onValueChange={onChange}>
            <SelectTrigger id={id}>
                <SelectValue placeholder={placeholder} />
            </SelectTrigger>
            <SelectContent>
                {normalised.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                        {o.label}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
    return (
        <div className="col-span-full">
            <Separator className="mt-2 mb-4" />
            <h3 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
                {children}
            </h3>
        </div>
    );
}

// ─── Type-specific attribute sections ────────────────────────────────────────

function PoliticalEntitySection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Political Entity Details</SectionHeading>
            <FieldWrapper
                label="Political Subtype"
                htmlFor="attr_political_subtype"
                error={errors['attributes.political_subtype']}
            >
                <EnumSelect
                    id="attr_political_subtype"
                    value={data.attr_political_subtype ?? ''}
                    onChange={(v) => onChange('attr_political_subtype', v)}
                    options={POLITICAL_ENTITY_SUBTYPES}
                    placeholder="Select subtype"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Government Type"
                htmlFor="attr_government_type"
                error={errors['attributes.government_type']}
            >
                <EnumSelect
                    id="attr_government_type"
                    value={data.attr_government_type ?? ''}
                    onChange={(v) => onChange('attr_government_type', v)}
                    options={GOVERNMENT_TYPES}
                    placeholder="Select government type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Succession Type"
                htmlFor="attr_succession_type"
                error={errors['attributes.succession_type']}
            >
                <EnumSelect
                    id="attr_succession_type"
                    value={data.attr_succession_type ?? ''}
                    onChange={(v) => onChange('attr_succession_type', v)}
                    options={SUCCESSION_TYPES}
                    placeholder="Select succession type"
                />
            </FieldWrapper>
        </>
    );
}

function DynastySection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Dynasty Details</SectionHeading>
            <FieldWrapper
                label="Government Type"
                htmlFor="attr_government_type"
                error={errors['attributes.government_type']}
            >
                <EnumSelect
                    id="attr_government_type"
                    value={data.attr_government_type ?? ''}
                    onChange={(v) => onChange('attr_government_type', v)}
                    options={GOVERNMENT_TYPES}
                    placeholder="Select government type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Succession Type"
                htmlFor="attr_succession_type"
                error={errors['attributes.succession_type']}
            >
                <EnumSelect
                    id="attr_succession_type"
                    value={data.attr_succession_type ?? ''}
                    onChange={(v) => onChange('attr_succession_type', v)}
                    options={SUCCESSION_TYPES}
                    placeholder="Select succession type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Founding Event"
                htmlFor="attr_founding_event"
                error={errors['attributes.founding_event']}
            >
                <Input
                    id="attr_founding_event"
                    value={data.attr_founding_event ?? ''}
                    onChange={(e) =>
                        onChange('attr_founding_event', e.target.value)
                    }
                    placeholder="Brief description of founding"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Ethnic Origin"
                htmlFor="attr_ethnic_origin"
                error={errors['attributes.ethnic_origin']}
            >
                <Input
                    id="attr_ethnic_origin"
                    value={data.attr_ethnic_origin ?? ''}
                    onChange={(e) =>
                        onChange('attr_ethnic_origin', e.target.value)
                    }
                    placeholder="e.g. Frankish"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Legitimacy Basis"
                htmlFor="attr_legitimacy_basis"
                error={errors['attributes.legitimacy_basis']}
            >
                <Input
                    id="attr_legitimacy_basis"
                    value={data.attr_legitimacy_basis ?? ''}
                    onChange={(e) =>
                        onChange('attr_legitimacy_basis', e.target.value)
                    }
                    placeholder="e.g. divine right, hereditary"
                />
            </FieldWrapper>
        </>
    );
}

function PersonSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Person Details</SectionHeading>
            <FieldWrapper
                label="Gender"
                htmlFor="attr_gender"
                error={errors['attributes.gender']}
            >
                <EnumSelect
                    id="attr_gender"
                    value={data.attr_gender ?? ''}
                    onChange={(v) => onChange('attr_gender', v)}
                    options={GENDERS}
                    placeholder="Select gender"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Birth Date (EDTF)"
                htmlFor="attr_birth_date"
                error={errors['attributes.birth_date']}
            >
                <Input
                    id="attr_birth_date"
                    value={data.attr_birth_date ?? ''}
                    onChange={(e) =>
                        onChange('attr_birth_date', e.target.value)
                    }
                    placeholder="e.g. -356 or 1452"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Death Date (EDTF)"
                htmlFor="attr_death_date"
                error={errors['attributes.death_date']}
            >
                <Input
                    id="attr_death_date"
                    value={data.attr_death_date ?? ''}
                    onChange={(e) =>
                        onChange('attr_death_date', e.target.value)
                    }
                    placeholder="e.g. -323 or 1519"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Ethnicity"
                htmlFor="attr_ethnicity"
                error={errors['attributes.ethnicity']}
            >
                <Input
                    id="attr_ethnicity"
                    value={data.attr_ethnicity ?? ''}
                    onChange={(e) => onChange('attr_ethnicity', e.target.value)}
                    placeholder="e.g. Macedonian"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Cause of Death"
                htmlFor="attr_cause_of_death"
                error={errors['attributes.cause_of_death']}
            >
                <Input
                    id="attr_cause_of_death"
                    value={data.attr_cause_of_death ?? ''}
                    onChange={(e) =>
                        onChange('attr_cause_of_death', e.target.value)
                    }
                    placeholder="e.g. fever, assassination"
                />
            </FieldWrapper>
        </>
    );
}

function MilitaryUnitSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Military Unit Details</SectionHeading>
            <FieldWrapper
                label="Unit Subtype"
                htmlFor="attr_unit_subtype"
                error={errors['attributes.unit_subtype']}
            >
                <EnumSelect
                    id="attr_unit_subtype"
                    value={data.attr_unit_subtype ?? ''}
                    onChange={(v) => onChange('attr_unit_subtype', v)}
                    options={MILITARY_UNIT_SUBTYPES}
                    placeholder="Select unit type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Composition"
                htmlFor="attr_composition"
                error={errors['attributes.composition']}
            >
                <EnumSelect
                    id="attr_composition"
                    value={data.attr_composition ?? ''}
                    onChange={(v) => onChange('attr_composition', v)}
                    options={MILITARY_COMPOSITIONS}
                    placeholder="Select composition"
                />
            </FieldWrapper>
        </>
    );
}

function DiplomaticRelationshipSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Diplomatic Relationship Details</SectionHeading>
            <FieldWrapper
                label="Diplomatic Status"
                htmlFor="attr_diplomatic_status"
                error={errors['attributes.diplomatic_status']}
            >
                <EnumSelect
                    id="attr_diplomatic_status"
                    value={data.attr_diplomatic_status ?? ''}
                    onChange={(v) => onChange('attr_diplomatic_status', v)}
                    options={DIPLOMATIC_STATUSES}
                    placeholder="Select status"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Terms"
                htmlFor="attr_terms"
                error={errors['attributes.terms']}
            >
                <Textarea
                    id="attr_terms"
                    value={data.attr_terms ?? ''}
                    onChange={(e) => onChange('attr_terms', e.target.value)}
                    placeholder="Key terms of the relationship"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Power Asymmetry"
                htmlFor="attr_power_asymmetry"
                error={errors['attributes.power_asymmetry']}
            >
                <Input
                    id="attr_power_asymmetry"
                    value={data.attr_power_asymmetry ?? ''}
                    onChange={(e) =>
                        onChange('attr_power_asymmetry', e.target.value)
                    }
                    placeholder="Description of power imbalance"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Military Obligations"
                htmlFor="attr_military_obligations"
                error={errors['attributes.military_obligations']}
            >
                <Input
                    id="attr_military_obligations"
                    value={data.attr_military_obligations ?? ''}
                    onChange={(e) =>
                        onChange('attr_military_obligations', e.target.value)
                    }
                    placeholder="e.g. mutual defense"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Termination Cause"
                htmlFor="attr_termination_cause"
                error={errors['attributes.termination_cause']}
            >
                <Input
                    id="attr_termination_cause"
                    value={data.attr_termination_cause ?? ''}
                    onChange={(e) =>
                        onChange('attr_termination_cause', e.target.value)
                    }
                    placeholder="How/why did it end?"
                />
            </FieldWrapper>
        </>
    );
}

function SocialClassSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Social Class Details</SectionHeading>
            <FieldWrapper
                label="Class Subtype"
                htmlFor="attr_class_subtype"
                error={errors['attributes.class_subtype']}
            >
                <EnumSelect
                    id="attr_class_subtype"
                    value={data.attr_class_subtype ?? ''}
                    onChange={(v) => onChange('attr_class_subtype', v)}
                    options={SOCIAL_CLASS_SUBTYPES}
                    placeholder="Select class type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Economic Role"
                htmlFor="attr_economic_role"
                error={errors['attributes.economic_role']}
            >
                <Input
                    id="attr_economic_role"
                    value={data.attr_economic_role ?? ''}
                    onChange={(e) =>
                        onChange('attr_economic_role', e.target.value)
                    }
                    placeholder="e.g. tax farmers, landowners"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Legal Status"
                htmlFor="attr_legal_status"
                error={errors['attributes.legal_status']}
            >
                <Input
                    id="attr_legal_status"
                    value={data.attr_legal_status ?? ''}
                    onChange={(e) =>
                        onChange('attr_legal_status', e.target.value)
                    }
                    placeholder="e.g. freemen, slaves"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Political Power"
                htmlFor="attr_political_power"
                error={errors['attributes.political_power']}
            >
                <Input
                    id="attr_political_power"
                    value={data.attr_political_power ?? ''}
                    onChange={(e) =>
                        onChange('attr_political_power', e.target.value)
                    }
                    placeholder="e.g. voting rights, senate access"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Social Mobility"
                htmlFor="attr_social_mobility"
                error={errors['attributes.social_mobility']}
            >
                <Input
                    id="attr_social_mobility"
                    value={data.attr_social_mobility ?? ''}
                    onChange={(e) =>
                        onChange('attr_social_mobility', e.target.value)
                    }
                    placeholder="e.g. low / high"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Military Obligation"
                htmlFor="attr_military_obligation"
                error={errors['attributes.military_obligation']}
            >
                <Input
                    id="attr_military_obligation"
                    value={data.attr_military_obligation ?? ''}
                    onChange={(e) =>
                        onChange('attr_military_obligation', e.target.value)
                    }
                    placeholder="e.g. mandatory service"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Education Access"
                htmlFor="attr_education_access"
                error={errors['attributes.education_access']}
            >
                <Input
                    id="attr_education_access"
                    value={data.attr_education_access ?? ''}
                    onChange={(e) =>
                        onChange('attr_education_access', e.target.value)
                    }
                    placeholder="e.g. restricted to clergy"
                />
            </FieldWrapper>
        </>
    );
}

function CitySection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>City / Settlement Details</SectionHeading>
            <FieldWrapper
                label="Settlement Subtype"
                htmlFor="attr_settlement_subtype"
                error={errors['attributes.settlement_subtype']}
            >
                <EnumSelect
                    id="attr_settlement_subtype"
                    value={data.attr_settlement_subtype ?? ''}
                    onChange={(v) => onChange('attr_settlement_subtype', v)}
                    options={SETTLEMENT_SUBTYPES}
                    placeholder="Select settlement type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Elevation (m)"
                htmlFor="attr_elevation_m"
                error={errors['attributes.elevation_m']}
            >
                <Input
                    id="attr_elevation_m"
                    type="number"
                    value={data.attr_elevation_m ?? ''}
                    onChange={(e) =>
                        onChange('attr_elevation_m', e.target.value)
                    }
                    placeholder="e.g. 21"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Founding Legend"
                htmlFor="attr_founding_legend"
                error={errors['attributes.founding_legend']}
            >
                <Textarea
                    id="attr_founding_legend"
                    value={data.attr_founding_legend ?? ''}
                    onChange={(e) =>
                        onChange('attr_founding_legend', e.target.value)
                    }
                    placeholder="Brief founding story or myth"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

function InfrastructureMonumentSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Infrastructure / Monument Details</SectionHeading>
            <FieldWrapper
                label="Monument Subtype"
                htmlFor="attr_monument_subtype"
                error={errors['attributes.monument_subtype']}
            >
                <EnumSelect
                    id="attr_monument_subtype"
                    value={data.attr_monument_subtype ?? ''}
                    onChange={(v) => onChange('attr_monument_subtype', v)}
                    options={MONUMENT_SUBTYPES}
                    placeholder="Select monument type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Construction Start (EDTF)"
                htmlFor="attr_construction_start"
                error={errors['attributes.construction_start']}
            >
                <Input
                    id="attr_construction_start"
                    value={data.attr_construction_start ?? ''}
                    onChange={(e) =>
                        onChange('attr_construction_start', e.target.value)
                    }
                    placeholder="e.g. -447"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Construction End (EDTF)"
                htmlFor="attr_construction_end"
                error={errors['attributes.construction_end']}
            >
                <Input
                    id="attr_construction_end"
                    value={data.attr_construction_end ?? ''}
                    onChange={(e) =>
                        onChange('attr_construction_end', e.target.value)
                    }
                    placeholder="e.g. -432"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Current Condition"
                htmlFor="attr_current_condition"
                error={errors['attributes.current_condition']}
            >
                <EnumSelect
                    id="attr_current_condition"
                    value={data.attr_current_condition ?? ''}
                    onChange={(v) => onChange('attr_current_condition', v)}
                    options={MONUMENT_CONDITIONS}
                    placeholder="Select condition"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Destruction Date (EDTF)"
                htmlFor="attr_destruction_date"
                error={errors['attributes.destruction_date']}
            >
                <Input
                    id="attr_destruction_date"
                    value={data.attr_destruction_date ?? ''}
                    onChange={(e) =>
                        onChange('attr_destruction_date', e.target.value)
                    }
                    placeholder="e.g. 80 or 1453"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Destruction Cause"
                htmlFor="attr_destruction_cause"
                error={errors['attributes.destruction_cause']}
            >
                <Input
                    id="attr_destruction_cause"
                    value={data.attr_destruction_cause ?? ''}
                    onChange={(e) =>
                        onChange('attr_destruction_cause', e.target.value)
                    }
                    placeholder="e.g. fire, earthquake, sack"
                />
            </FieldWrapper>
            <FieldWrapper
                label="UNESCO Status"
                htmlFor="attr_unesco_status"
                error={errors['attributes.unesco_status']}
            >
                <Input
                    id="attr_unesco_status"
                    value={data.attr_unesco_status ?? ''}
                    onChange={(e) =>
                        onChange('attr_unesco_status', e.target.value)
                    }
                    placeholder="e.g. World Heritage Site"
                />
            </FieldWrapper>
        </>
    );
}

function ExtractionInfraSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Extraction Infrastructure Details</SectionHeading>
            <FieldWrapper
                label="Infrastructure Subtype"
                htmlFor="attr_infra_subtype"
                error={errors['attributes.infra_subtype']}
            >
                <EnumSelect
                    id="attr_infra_subtype"
                    value={data.attr_infra_subtype ?? ''}
                    onChange={(v) => onChange('attr_infra_subtype', v)}
                    options={EXTRACTION_INFRA_SUBTYPES}
                    placeholder="Select infrastructure type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Scale"
                htmlFor="attr_scale"
                error={errors['attributes.scale']}
            >
                <EnumSelect
                    id="attr_scale"
                    value={data.attr_scale ?? ''}
                    onChange={(v) => onChange('attr_scale', v)}
                    options={EXTRACTION_SCALES}
                    placeholder="Select scale"
                />
            </FieldWrapper>
        </>
    );
}

function EducationalInstitutionSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Educational Institution Details</SectionHeading>
            <FieldWrapper
                label="Institution Type"
                htmlFor="attr_institution_type"
                error={errors['attributes.institution_type']}
            >
                <Input
                    id="attr_institution_type"
                    value={data.attr_institution_type ?? ''}
                    onChange={(e) =>
                        onChange('attr_institution_type', e.target.value)
                    }
                    placeholder="e.g. academy, university, library, madrasa"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Library Holdings"
                htmlFor="attr_library_holdings"
                error={errors['attributes.library_holdings']}
            >
                <Input
                    id="attr_library_holdings"
                    value={data.attr_library_holdings ?? ''}
                    onChange={(e) =>
                        onChange('attr_library_holdings', e.target.value)
                    }
                    placeholder="Description of holdings"
                />
            </FieldWrapper>
        </>
    );
}

function EventWarSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>War / Conflict Details</SectionHeading>
            <FieldWrapper
                label="War Subtype"
                htmlFor="attr_war_subtype"
                error={errors['attributes.war_subtype']}
            >
                <EnumSelect
                    id="attr_war_subtype"
                    value={data.attr_war_subtype ?? ''}
                    onChange={(v) => onChange('attr_war_subtype', v)}
                    options={WAR_SUBTYPES}
                    placeholder="Select war type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Casus Belli"
                htmlFor="attr_casus_belli"
                error={errors['attributes.casus_belli']}
            >
                <Textarea
                    id="attr_casus_belli"
                    value={data.attr_casus_belli ?? ''}
                    onChange={(e) =>
                        onChange('attr_casus_belli', e.target.value)
                    }
                    placeholder="Stated or real reason for war"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Territorial Changes"
                htmlFor="attr_territorial_changes"
                error={errors['attributes.territorial_changes']}
            >
                <Textarea
                    id="attr_territorial_changes"
                    value={data.attr_territorial_changes ?? ''}
                    onChange={(e) =>
                        onChange('attr_territorial_changes', e.target.value)
                    }
                    placeholder="Summary of territory gained or lost"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

function EventBattleSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Battle Details</SectionHeading>
            <FieldWrapper
                label="Battle Subtype"
                htmlFor="attr_battle_subtype"
                error={errors['attributes.battle_subtype']}
            >
                <EnumSelect
                    id="attr_battle_subtype"
                    value={data.attr_battle_subtype ?? ''}
                    onChange={(v) => onChange('attr_battle_subtype', v)}
                    options={BATTLE_SUBTYPES}
                    placeholder="Select battle type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Outcome"
                htmlFor="attr_outcome"
                error={errors['attributes.outcome']}
            >
                <EnumSelect
                    id="attr_outcome"
                    value={data.attr_outcome ?? ''}
                    onChange={(v) => onChange('attr_outcome', v)}
                    options={BATTLE_OUTCOMES}
                    placeholder="Select outcome"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Victor Side"
                htmlFor="attr_victor_side"
                error={errors['attributes.victor_side']}
            >
                <Input
                    id="attr_victor_side"
                    value={data.attr_victor_side ?? ''}
                    onChange={(e) =>
                        onChange('attr_victor_side', e.target.value)
                    }
                    placeholder="e.g. side_a or name"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Tactical Notes"
                htmlFor="attr_tactical_notes"
                error={errors['attributes.tactical_notes']}
            >
                <Textarea
                    id="attr_tactical_notes"
                    value={data.attr_tactical_notes ?? ''}
                    onChange={(e) =>
                        onChange('attr_tactical_notes', e.target.value)
                    }
                    placeholder="Key tactical details"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

function EventTreatySection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Treaty / Agreement Details</SectionHeading>
            <FieldWrapper
                label="Treaty Subtype"
                htmlFor="attr_treaty_subtype"
                error={errors['attributes.treaty_subtype']}
            >
                <EnumSelect
                    id="attr_treaty_subtype"
                    value={data.attr_treaty_subtype ?? ''}
                    onChange={(v) => onChange('attr_treaty_subtype', v)}
                    options={TREATY_SUBTYPES}
                    placeholder="Select treaty type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Key Provisions"
                htmlFor="attr_key_provisions"
                error={errors['attributes.key_provisions']}
            >
                <Textarea
                    id="attr_key_provisions"
                    value={data.attr_key_provisions ?? ''}
                    onChange={(e) =>
                        onChange('attr_key_provisions', e.target.value)
                    }
                    placeholder="Main terms of the agreement"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Duration"
                htmlFor="attr_duration"
                error={errors['attributes.duration']}
            >
                <Input
                    id="attr_duration"
                    value={data.attr_duration ?? ''}
                    onChange={(e) => onChange('attr_duration', e.target.value)}
                    placeholder="e.g. 50 years, perpetual"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Termination Date (EDTF)"
                htmlFor="attr_termination_date"
                error={errors['attributes.termination_date']}
            >
                <Input
                    id="attr_termination_date"
                    value={data.attr_termination_date ?? ''}
                    onChange={(e) =>
                        onChange('attr_termination_date', e.target.value)
                    }
                    placeholder="e.g. 200"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Termination Reason"
                htmlFor="attr_termination_reason"
                error={errors['attributes.termination_reason']}
            >
                <Input
                    id="attr_termination_reason"
                    value={data.attr_termination_reason ?? ''}
                    onChange={(e) =>
                        onChange('attr_termination_reason', e.target.value)
                    }
                    placeholder="Why the treaty ended"
                />
            </FieldWrapper>
        </>
    );
}

function EventRebellionSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Rebellion / Revolution Details</SectionHeading>
            <FieldWrapper
                label="Rebellion Subtype"
                htmlFor="attr_rebellion_subtype"
                error={errors['attributes.rebellion_subtype']}
            >
                <EnumSelect
                    id="attr_rebellion_subtype"
                    value={data.attr_rebellion_subtype ?? ''}
                    onChange={(v) => onChange('attr_rebellion_subtype', v)}
                    options={REBELLION_SUBTYPES}
                    placeholder="Select rebellion type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Outcome"
                htmlFor="attr_outcome"
                error={errors['attributes.outcome']}
            >
                <EnumSelect
                    id="attr_outcome"
                    value={data.attr_outcome ?? ''}
                    onChange={(v) => onChange('attr_outcome', v)}
                    options={REBELLION_OUTCOMES}
                    placeholder="Select outcome"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Government Change"
                htmlFor="attr_government_change"
                error={errors['attributes.government_change']}
            >
                <Input
                    id="attr_government_change"
                    value={data.attr_government_change ?? ''}
                    onChange={(e) =>
                        onChange('attr_government_change', e.target.value)
                    }
                    placeholder="What changed after the rebellion"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Repression"
                htmlFor="attr_repression"
                error={errors['attributes.repression']}
            >
                <Input
                    id="attr_repression"
                    value={data.attr_repression ?? ''}
                    onChange={(e) =>
                        onChange('attr_repression', e.target.value)
                    }
                    placeholder="How was the rebellion suppressed?"
                />
            </FieldWrapper>
        </>
    );
}

function EventNaturalDisasterSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Natural Disaster Details</SectionHeading>
            <FieldWrapper
                label="Disaster Subtype"
                htmlFor="attr_disaster_subtype"
                error={errors['attributes.disaster_subtype']}
            >
                <EnumSelect
                    id="attr_disaster_subtype"
                    value={data.attr_disaster_subtype ?? ''}
                    onChange={(v) => onChange('attr_disaster_subtype', v)}
                    options={DISASTER_SUBTYPES}
                    placeholder="Select disaster type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Economic Damage"
                htmlFor="attr_economic_damage"
                error={errors['attributes.economic_damage']}
            >
                <Input
                    id="attr_economic_damage"
                    value={data.attr_economic_damage ?? ''}
                    onChange={(e) =>
                        onChange('attr_economic_damage', e.target.value)
                    }
                    placeholder="Description of economic damage"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Societal Response"
                htmlFor="attr_societal_response"
                error={errors['attributes.societal_response']}
            >
                <Textarea
                    id="attr_societal_response"
                    value={data.attr_societal_response ?? ''}
                    onChange={(e) =>
                        onChange('attr_societal_response', e.target.value)
                    }
                    placeholder="How did society respond?"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Long-term Consequences"
                htmlFor="attr_long_term_consequences"
                error={errors['attributes.long_term_consequences']}
            >
                <Textarea
                    id="attr_long_term_consequences"
                    value={data.attr_long_term_consequences ?? ''}
                    onChange={(e) =>
                        onChange('attr_long_term_consequences', e.target.value)
                    }
                    placeholder="Lasting historical effects"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

function EventTechAdoptionSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Technology Adoption Details</SectionHeading>
            <FieldWrapper
                label="Acquisition Method"
                htmlFor="attr_acquisition_method"
                error={errors['attributes.acquisition_method']}
            >
                <EnumSelect
                    id="attr_acquisition_method"
                    value={data.attr_acquisition_method ?? ''}
                    onChange={(v) => onChange('attr_acquisition_method', v)}
                    options={TECH_ADOPTION_METHODS}
                    placeholder="How was it acquired?"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Diffusion Speed"
                htmlFor="attr_diffusion_speed"
                error={errors['attributes.diffusion_speed']}
            >
                <EnumSelect
                    id="attr_diffusion_speed"
                    value={data.attr_diffusion_speed ?? ''}
                    onChange={(v) => onChange('attr_diffusion_speed', v)}
                    options={DIFFUSION_SPEEDS}
                    placeholder="How quickly did it spread?"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Adaptation Notes"
                htmlFor="attr_adaptation_notes"
                error={errors['attributes.adaptation_notes']}
            >
                <Textarea
                    id="attr_adaptation_notes"
                    value={data.attr_adaptation_notes ?? ''}
                    onChange={(e) =>
                        onChange('attr_adaptation_notes', e.target.value)
                    }
                    placeholder="Local adaptations or modifications"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Impact"
                htmlFor="attr_impact"
                error={errors['attributes.impact']}
            >
                <Textarea
                    id="attr_impact"
                    value={data.attr_impact ?? ''}
                    onChange={(e) => onChange('attr_impact', e.target.value)}
                    placeholder="Historical impact of the adoption"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

function EventLegalReformSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>
                Legal / Institutional Reform Details
            </SectionHeading>
            <FieldWrapper
                label="Reform Subtype"
                htmlFor="attr_reform_subtype"
                error={errors['attributes.reform_subtype']}
            >
                <EnumSelect
                    id="attr_reform_subtype"
                    value={data.attr_reform_subtype ?? ''}
                    onChange={(v) => onChange('attr_reform_subtype', v)}
                    options={REFORM_SUBTYPES}
                    placeholder="Select reform type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Provisions"
                htmlFor="attr_provisions"
                error={errors['attributes.provisions']}
            >
                <Textarea
                    id="attr_provisions"
                    value={data.attr_provisions ?? ''}
                    onChange={(e) =>
                        onChange('attr_provisions', e.target.value)
                    }
                    placeholder="Main provisions of the reform"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Motivation"
                htmlFor="attr_motivation"
                error={errors['attributes.motivation']}
            >
                <Textarea
                    id="attr_motivation"
                    value={data.attr_motivation ?? ''}
                    onChange={(e) =>
                        onChange('attr_motivation', e.target.value)
                    }
                    placeholder="Political or social motivation"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Longevity"
                htmlFor="attr_longevity"
                error={errors['attributes.longevity']}
            >
                <Input
                    id="attr_longevity"
                    value={data.attr_longevity ?? ''}
                    onChange={(e) => onChange('attr_longevity', e.target.value)}
                    placeholder="How long did it last?"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Intended Effects"
                htmlFor="attr_effects_intended"
                error={errors['attributes.effects_intended']}
            >
                <Textarea
                    id="attr_effects_intended"
                    value={data.attr_effects_intended ?? ''}
                    onChange={(e) =>
                        onChange('attr_effects_intended', e.target.value)
                    }
                    placeholder="Planned outcomes"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Unintended Effects"
                htmlFor="attr_effects_unintended"
                error={errors['attributes.effects_unintended']}
            >
                <Textarea
                    id="attr_effects_unintended"
                    value={data.attr_effects_unintended ?? ''}
                    onChange={(e) =>
                        onChange('attr_effects_unintended', e.target.value)
                    }
                    placeholder="Unexpected consequences"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Reversal Date (EDTF)"
                htmlFor="attr_reversal_date"
                error={errors['attributes.reversal_date']}
            >
                <Input
                    id="attr_reversal_date"
                    value={data.attr_reversal_date ?? ''}
                    onChange={(e) =>
                        onChange('attr_reversal_date', e.target.value)
                    }
                    placeholder="When was it reversed?"
                />
            </FieldWrapper>
        </>
    );
}

function EpidemicDiseaseSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Epidemic / Disease Details</SectionHeading>
            <FieldWrapper
                label="Epidemic Subtype"
                htmlFor="attr_epidemic_subtype"
                error={errors['attributes.epidemic_subtype']}
            >
                <EnumSelect
                    id="attr_epidemic_subtype"
                    value={data.attr_epidemic_subtype ?? ''}
                    onChange={(v) => onChange('attr_epidemic_subtype', v)}
                    options={EPIDEMIC_SUBTYPES}
                    placeholder="Select disease type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Severity"
                htmlFor="attr_severity"
                error={errors['attributes.severity']}
            >
                <EnumSelect
                    id="attr_severity"
                    value={data.attr_severity ?? ''}
                    onChange={(v) => onChange('attr_severity', v)}
                    options={EPIDEMIC_SEVERITIES}
                    placeholder="Select severity"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Spread Vector"
                htmlFor="attr_spread_vector"
                error={errors['attributes.spread_vector']}
            >
                <Input
                    id="attr_spread_vector"
                    value={data.attr_spread_vector ?? ''}
                    onChange={(e) =>
                        onChange('attr_spread_vector', e.target.value)
                    }
                    placeholder="e.g. fleas/rats, water, airborne"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Societal Responses"
                htmlFor="attr_societal_responses"
                error={errors['attributes.societal_responses']}
            >
                <Textarea
                    id="attr_societal_responses"
                    value={data.attr_societal_responses ?? ''}
                    onChange={(e) =>
                        onChange('attr_societal_responses', e.target.value)
                    }
                    placeholder="How did society respond?"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Economic Consequences"
                htmlFor="attr_economic_consequences"
                error={errors['attributes.economic_consequences']}
            >
                <Textarea
                    id="attr_economic_consequences"
                    value={data.attr_economic_consequences ?? ''}
                    onChange={(e) =>
                        onChange('attr_economic_consequences', e.target.value)
                    }
                    placeholder="Economic effects of the epidemic"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

function MigrationSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Migration Details</SectionHeading>
            <FieldWrapper
                label="Migration Subtype"
                htmlFor="attr_migration_subtype"
                error={errors['attributes.migration_subtype']}
            >
                <EnumSelect
                    id="attr_migration_subtype"
                    value={data.attr_migration_subtype ?? ''}
                    onChange={(v) => onChange('attr_migration_subtype', v)}
                    options={MIGRATION_SUBTYPES}
                    placeholder="Select migration type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Migrating Group"
                htmlFor="attr_migrating_group"
                error={errors['attributes.migrating_group']}
            >
                <Input
                    id="attr_migrating_group"
                    value={data.attr_migrating_group ?? ''}
                    onChange={(e) =>
                        onChange('attr_migrating_group', e.target.value)
                    }
                    placeholder="Name of the migrating people"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Casualties During Migration"
                htmlFor="attr_casualties_during"
                error={errors['attributes.casualties_during']}
            >
                <Input
                    id="attr_casualties_during"
                    value={data.attr_casualties_during ?? ''}
                    onChange={(e) =>
                        onChange('attr_casualties_during', e.target.value)
                    }
                    placeholder="Description of casualties"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Impact on Origin Region"
                htmlFor="attr_impact_origin"
                error={errors['attributes.impact_origin']}
            >
                <Textarea
                    id="attr_impact_origin"
                    value={data.attr_impact_origin ?? ''}
                    onChange={(e) =>
                        onChange('attr_impact_origin', e.target.value)
                    }
                    placeholder="Effects on the region of origin"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Impact on Destination Region"
                htmlFor="attr_impact_destination"
                error={errors['attributes.impact_destination']}
            >
                <Textarea
                    id="attr_impact_destination"
                    value={data.attr_impact_destination ?? ''}
                    onChange={(e) =>
                        onChange('attr_impact_destination', e.target.value)
                    }
                    placeholder="Effects on the destination region"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

function TradeRouteSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Trade Route Details</SectionHeading>
            <FieldWrapper
                label="Route Subtype"
                htmlFor="attr_route_subtype"
                error={errors['attributes.route_subtype']}
            >
                <EnumSelect
                    id="attr_route_subtype"
                    value={data.attr_route_subtype ?? ''}
                    onChange={(v) => onChange('attr_route_subtype', v)}
                    options={TRADE_ROUTE_SUBTYPES}
                    placeholder="Select route type"
                />
            </FieldWrapper>
        </>
    );
}

function NaturalResourceSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Natural Resource Details</SectionHeading>
            <FieldWrapper
                label="Resource Category"
                htmlFor="attr_resource_category"
                error={errors['attributes.resource_category']}
            >
                <EnumSelect
                    id="attr_resource_category"
                    value={data.attr_resource_category ?? ''}
                    onChange={(v) => onChange('attr_resource_category', v)}
                    options={RESOURCE_CATEGORIES}
                    placeholder="Select category"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Renewability"
                htmlFor="attr_renewability"
                error={errors['attributes.renewability']}
            >
                <EnumSelect
                    id="attr_renewability"
                    value={data.attr_renewability ?? ''}
                    onChange={(v) => onChange('attr_renewability', v)}
                    options={RESOURCE_RENEWABILITIES}
                    placeholder="Select renewability"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Substitutability"
                htmlFor="attr_substitutability"
                error={errors['attributes.substitutability']}
            >
                <Input
                    id="attr_substitutability"
                    value={data.attr_substitutability ?? ''}
                    onChange={(e) =>
                        onChange('attr_substitutability', e.target.value)
                    }
                    placeholder="Can it be substituted? How?"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Transport Difficulty"
                htmlFor="attr_transport_difficulty"
                error={errors['attributes.transport_difficulty']}
            >
                <Input
                    id="attr_transport_difficulty"
                    value={data.attr_transport_difficulty ?? ''}
                    onChange={(e) =>
                        onChange('attr_transport_difficulty', e.target.value)
                    }
                    placeholder="Description of transport challenges"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Cultural Value"
                htmlFor="attr_cultural_value"
                error={errors['attributes.cultural_value']}
            >
                <Input
                    id="attr_cultural_value"
                    value={data.attr_cultural_value ?? ''}
                    onChange={(e) =>
                        onChange('attr_cultural_value', e.target.value)
                    }
                    placeholder="Ritual or prestige significance"
                />
            </FieldWrapper>
        </>
    );
}

function CurrencyMonetarySystemSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Currency / Monetary System Details</SectionHeading>
            <FieldWrapper
                label="Currency Type"
                htmlFor="attr_currency_type"
                error={errors['attributes.currency_type']}
            >
                <EnumSelect
                    id="attr_currency_type"
                    value={data.attr_currency_type ?? ''}
                    onChange={(v) => onChange('attr_currency_type', v)}
                    options={CURRENCY_TYPES}
                    placeholder="Select currency type"
                />
            </FieldWrapper>
        </>
    );
}

function CulturalWorkSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Cultural / Artistic Work Details</SectionHeading>
            <FieldWrapper
                label="Work Subtype"
                htmlFor="attr_work_subtype"
                error={errors['attributes.work_subtype']}
            >
                <EnumSelect
                    id="attr_work_subtype"
                    value={data.attr_work_subtype ?? ''}
                    onChange={(v) => onChange('attr_work_subtype', v)}
                    options={CULTURAL_WORK_SUBTYPES}
                    placeholder="Select work type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Style / Genre"
                htmlFor="attr_style_genre"
                error={errors['attributes.style_genre']}
            >
                <Input
                    id="attr_style_genre"
                    value={data.attr_style_genre ?? ''}
                    onChange={(e) =>
                        onChange('attr_style_genre', e.target.value)
                    }
                    placeholder="e.g. epic poetry, naturalist sculpture"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Preservation Status"
                htmlFor="attr_preservation_status"
                error={errors['attributes.preservation_status']}
            >
                <EnumSelect
                    id="attr_preservation_status"
                    value={data.attr_preservation_status ?? ''}
                    onChange={(v) => onChange('attr_preservation_status', v)}
                    options={PRESERVATION_STATUSES}
                    placeholder="Select status"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Current Location"
                htmlFor="attr_current_location"
                error={errors['attributes.current_location']}
            >
                <Input
                    id="attr_current_location"
                    value={data.attr_current_location ?? ''}
                    onChange={(e) =>
                        onChange('attr_current_location', e.target.value)
                    }
                    placeholder="e.g. British Museum, London"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Influence Description"
                htmlFor="attr_influence_description"
                error={errors['attributes.influence_description']}
            >
                <Textarea
                    id="attr_influence_description"
                    value={data.attr_influence_description ?? ''}
                    onChange={(e) =>
                        onChange('attr_influence_description', e.target.value)
                    }
                    placeholder="How did this work influence later culture?"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

function IntellectualMovementSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>
                Intellectual / Artistic Movement Details
            </SectionHeading>
            <FieldWrapper
                label="Movement Subtype"
                htmlFor="attr_intellectual_movement_subtype"
                error={errors['attributes.intellectual_movement_subtype']}
            >
                <EnumSelect
                    id="attr_intellectual_movement_subtype"
                    value={data.attr_intellectual_movement_subtype ?? ''}
                    onChange={(v) =>
                        onChange('attr_intellectual_movement_subtype', v)
                    }
                    options={INTELLECTUAL_MOVEMENT_SUBTYPES}
                    placeholder="Select subtype"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Core Ideas"
                htmlFor="attr_core_ideas"
                error={errors['attributes.core_ideas']}
            >
                <Textarea
                    id="attr_core_ideas"
                    value={data.attr_core_ideas ?? ''}
                    onChange={(e) =>
                        onChange('attr_core_ideas', e.target.value)
                    }
                    placeholder="Central tenets or principles"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Methodology"
                htmlFor="attr_methodology"
                error={errors['attributes.methodology']}
            >
                <Textarea
                    id="attr_methodology"
                    value={data.attr_methodology ?? ''}
                    onChange={(e) =>
                        onChange('attr_methodology', e.target.value)
                    }
                    placeholder="Approach or method used"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Style Characteristics"
                htmlFor="attr_style_characteristics"
                error={errors['attributes.style_characteristics']}
            >
                <Textarea
                    id="attr_style_characteristics"
                    value={data.attr_style_characteristics ?? ''}
                    onChange={(e) =>
                        onChange('attr_style_characteristics', e.target.value)
                    }
                    placeholder="Defining aesthetic or stylistic features"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

function ArchaeologicalCultureSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Archaeological Culture Details</SectionHeading>
            <FieldWrapper
                label="Technology Level"
                htmlFor="attr_technology_level"
                error={errors['attributes.technology_level']}
            >
                <Input
                    id="attr_technology_level"
                    value={data.attr_technology_level ?? ''}
                    onChange={(e) =>
                        onChange('attr_technology_level', e.target.value)
                    }
                    placeholder="e.g. Bronze Age, Neolithic"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Economic Base"
                htmlFor="attr_economic_base"
                error={errors['attributes.economic_base']}
            >
                <Input
                    id="attr_economic_base"
                    value={data.attr_economic_base ?? ''}
                    onChange={(e) =>
                        onChange('attr_economic_base', e.target.value)
                    }
                    placeholder="e.g. pastoralism, agriculture, trade"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Settlement Patterns"
                htmlFor="attr_settlement_patterns"
                error={errors['attributes.settlement_patterns']}
            >
                <Input
                    id="attr_settlement_patterns"
                    value={data.attr_settlement_patterns ?? ''}
                    onChange={(e) =>
                        onChange('attr_settlement_patterns', e.target.value)
                    }
                    placeholder="e.g. dispersed farmsteads, hillforts"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Burial Practices"
                htmlFor="attr_burial_practices"
                error={errors['attributes.burial_practices']}
            >
                <Input
                    id="attr_burial_practices"
                    value={data.attr_burial_practices ?? ''}
                    onChange={(e) =>
                        onChange('attr_burial_practices', e.target.value)
                    }
                    placeholder="e.g. inhumation, cremation, kurgan"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Hypothesized Ethnicity"
                htmlFor="attr_hypothesized_ethnicity"
                error={errors['attributes.hypothesized_ethnicity']}
            >
                <Input
                    id="attr_hypothesized_ethnicity"
                    value={data.attr_hypothesized_ethnicity ?? ''}
                    onChange={(e) =>
                        onChange('attr_hypothesized_ethnicity', e.target.value)
                    }
                    placeholder="Modern scholarly attribution"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Evidence Quality"
                htmlFor="attr_evidence_quality"
                error={errors['attributes.evidence_quality']}
            >
                <Input
                    id="attr_evidence_quality"
                    value={data.attr_evidence_quality ?? ''}
                    onChange={(e) =>
                        onChange('attr_evidence_quality', e.target.value)
                    }
                    placeholder="e.g. well-documented, sparse"
                />
            </FieldWrapper>
        </>
    );
}

function LanguageSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Language Details</SectionHeading>
            <FieldWrapper
                label="Language Status"
                htmlFor="attr_language_status"
                error={errors['attributes.language_status']}
            >
                <EnumSelect
                    id="attr_language_status"
                    value={data.attr_language_status ?? ''}
                    onChange={(v) => onChange('attr_language_status', v)}
                    options={LANGUAGE_STATUSES}
                    placeholder="Select status"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Language Family"
                htmlFor="attr_language_family"
                error={errors['attributes.language_family']}
            >
                <Input
                    id="attr_language_family"
                    value={data.attr_language_family ?? ''}
                    onChange={(e) =>
                        onChange('attr_language_family', e.target.value)
                    }
                    placeholder="e.g. Indo-European, Semitic"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Writing System"
                htmlFor="attr_writing_system"
                error={errors['attributes.writing_system']}
            >
                <Input
                    id="attr_writing_system"
                    value={data.attr_writing_system ?? ''}
                    onChange={(e) =>
                        onChange('attr_writing_system', e.target.value)
                    }
                    placeholder="e.g. cuneiform, Latin alphabet"
                />
            </FieldWrapper>
            <FieldWrapper
                label="ISO 639 Code"
                htmlFor="attr_iso_639_code"
                error={errors['attributes.iso_639_code']}
            >
                <Input
                    id="attr_iso_639_code"
                    value={data.attr_iso_639_code ?? ''}
                    onChange={(e) =>
                        onChange('attr_iso_639_code', e.target.value)
                    }
                    placeholder="e.g. lat, grc"
                />
            </FieldWrapper>
        </>
    );
}

function ReligiousTextSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>
                Religious Text / Sacred Object Details
            </SectionHeading>
            <FieldWrapper
                label="Text Type"
                htmlFor="attr_text_type"
                error={errors['attributes.text_type']}
            >
                <EnumSelect
                    id="attr_text_type"
                    value={data.attr_text_type ?? ''}
                    onChange={(v) => onChange('attr_text_type', v)}
                    options={RELIGIOUS_TEXT_TYPES}
                    placeholder="Select type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Genre"
                htmlFor="attr_genre"
                error={errors['attributes.genre']}
            >
                <EnumSelect
                    id="attr_genre"
                    value={data.attr_genre ?? ''}
                    onChange={(v) => onChange('attr_genre', v)}
                    options={RELIGIOUS_TEXT_GENRES}
                    placeholder="Select genre"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Composition Date (EDTF)"
                htmlFor="attr_composition_date"
                error={errors['attributes.composition_date']}
            >
                <Input
                    id="attr_composition_date"
                    value={data.attr_composition_date ?? ''}
                    onChange={(e) =>
                        onChange('attr_composition_date', e.target.value)
                    }
                    placeholder="e.g. -600"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Material"
                htmlFor="attr_material"
                error={errors['attributes.material']}
            >
                <Input
                    id="attr_material"
                    value={data.attr_material ?? ''}
                    onChange={(e) => onChange('attr_material', e.target.value)}
                    placeholder="e.g. papyrus, parchment, stone"
                />
            </FieldWrapper>
        </>
    );
}

function LegalCodeSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>
                Legal Code / Constitutional Document Details
            </SectionHeading>
            <FieldWrapper
                label="Promulgation Date (EDTF)"
                htmlFor="attr_promulgation_date"
                error={errors['attributes.promulgation_date']}
            >
                <Input
                    id="attr_promulgation_date"
                    value={data.attr_promulgation_date ?? ''}
                    onChange={(e) =>
                        onChange('attr_promulgation_date', e.target.value)
                    }
                    placeholder="e.g. -450"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Key Provisions"
                htmlFor="attr_key_provisions"
                error={errors['attributes.key_provisions']}
            >
                <Textarea
                    id="attr_key_provisions"
                    value={data.attr_key_provisions ?? ''}
                    onChange={(e) =>
                        onChange('attr_key_provisions', e.target.value)
                    }
                    placeholder="Main provisions of the code"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Legal Philosophy"
                htmlFor="attr_legal_philosophy"
                error={errors['attributes.legal_philosophy']}
            >
                <Textarea
                    id="attr_legal_philosophy"
                    value={data.attr_legal_philosophy ?? ''}
                    onChange={(e) =>
                        onChange('attr_legal_philosophy', e.target.value)
                    }
                    placeholder="Underlying legal principles"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Enforcement Duration"
                htmlFor="attr_enforcement_duration"
                error={errors['attributes.enforcement_duration']}
            >
                <Input
                    id="attr_enforcement_duration"
                    value={data.attr_enforcement_duration ?? ''}
                    onChange={(e) =>
                        onChange('attr_enforcement_duration', e.target.value)
                    }
                    placeholder="How long was it in force?"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Modern Significance"
                htmlFor="attr_modern_significance"
                error={errors['attributes.modern_significance']}
            >
                <Textarea
                    id="attr_modern_significance"
                    value={data.attr_modern_significance ?? ''}
                    onChange={(e) =>
                        onChange('attr_modern_significance', e.target.value)
                    }
                    placeholder="Influence on modern legal systems"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

function ReligiousMovementSection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Religious Movement Details</SectionHeading>
            <FieldWrapper
                label="Movement Subtype"
                htmlFor="attr_movement_subtype"
                error={errors['attributes.movement_subtype']}
            >
                <EnumSelect
                    id="attr_movement_subtype"
                    value={data.attr_movement_subtype ?? ''}
                    onChange={(v) => onChange('attr_movement_subtype', v)}
                    options={RELIGIOUS_MOVEMENT_SUBTYPES}
                    placeholder="Select movement type"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Core Doctrines"
                htmlFor="attr_core_doctrines"
                error={errors['attributes.core_doctrines']}
            >
                <Textarea
                    id="attr_core_doctrines"
                    value={data.attr_core_doctrines ?? ''}
                    onChange={(e) =>
                        onChange('attr_core_doctrines', e.target.value)
                    }
                    placeholder="Central beliefs and teachings"
                    rows={2}
                />
            </FieldWrapper>
            <FieldWrapper
                label="Institutional Structure"
                htmlFor="attr_institutional_structure"
                error={errors['attributes.institutional_structure']}
            >
                <Input
                    id="attr_institutional_structure"
                    value={data.attr_institutional_structure ?? ''}
                    onChange={(e) =>
                        onChange('attr_institutional_structure', e.target.value)
                    }
                    placeholder="e.g. church, temple network, decentralized"
                />
            </FieldWrapper>
        </>
    );
}

function TechnologySection({
    data,
    errors,
    onChange,
}: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Technology / Innovation Details</SectionHeading>
            <FieldWrapper
                label="Technology Domain"
                htmlFor="attr_tech_domain"
                error={errors['attributes.tech_domain']}
            >
                <EnumSelect
                    id="attr_tech_domain"
                    value={data.attr_tech_domain ?? ''}
                    onChange={(v) => onChange('attr_tech_domain', v)}
                    options={TECHNOLOGY_DOMAINS}
                    placeholder="Select domain"
                />
            </FieldWrapper>
            <FieldWrapper
                label="Impact Description"
                htmlFor="attr_impact_description"
                error={errors['attributes.impact_description']}
            >
                <Textarea
                    id="attr_impact_description"
                    value={data.attr_impact_description ?? ''}
                    onChange={(e) =>
                        onChange('attr_impact_description', e.target.value)
                    }
                    placeholder="Historical significance of this technology"
                    rows={2}
                />
            </FieldWrapper>
        </>
    );
}

// ─── Type-specific section router ─────────────────────────────────────────────

function TypeSpecificSection({
    entityType,
    data,
    errors,
    onChange,
}: { entityType: EntityType | '' } & Pick<
    Props,
    'data' | 'errors' | 'onChange'
>) {
    const sectionProps = { data, errors, onChange };

    switch (entityType) {
        case 'political_entity':
            return <PoliticalEntitySection {...sectionProps} />;
        case 'dynasty':
            return <DynastySection {...sectionProps} />;
        case 'person':
            return <PersonSection {...sectionProps} />;
        case 'military_unit':
            return <MilitaryUnitSection {...sectionProps} />;
        case 'diplomatic_relationship':
            return <DiplomaticRelationshipSection {...sectionProps} />;
        case 'social_class':
            return <SocialClassSection {...sectionProps} />;
        case 'city':
            return <CitySection {...sectionProps} />;
        case 'infrastructure_monument':
            return <InfrastructureMonumentSection {...sectionProps} />;
        case 'extraction_infra':
            return <ExtractionInfraSection {...sectionProps} />;
        case 'educational_institution':
            return <EducationalInstitutionSection {...sectionProps} />;
        case 'event_war':
            return <EventWarSection {...sectionProps} />;
        case 'event_battle':
            return <EventBattleSection {...sectionProps} />;
        case 'event_treaty':
            return <EventTreatySection {...sectionProps} />;
        case 'event_rebellion':
            return <EventRebellionSection {...sectionProps} />;
        case 'event_natural_disaster':
            return <EventNaturalDisasterSection {...sectionProps} />;
        case 'event_tech_adoption':
            return <EventTechAdoptionSection {...sectionProps} />;
        case 'event_legal_reform':
            return <EventLegalReformSection {...sectionProps} />;
        case 'epidemic_disease':
            return <EpidemicDiseaseSection {...sectionProps} />;
        case 'migration':
            return <MigrationSection {...sectionProps} />;
        case 'trade_route':
            return <TradeRouteSection {...sectionProps} />;
        case 'natural_resource':
            return <NaturalResourceSection {...sectionProps} />;
        case 'currency_monetary_system':
            return <CurrencyMonetarySystemSection {...sectionProps} />;
        case 'cultural_work':
            return <CulturalWorkSection {...sectionProps} />;
        case 'intellectual_movement':
            return <IntellectualMovementSection {...sectionProps} />;
        case 'archaeological_culture':
            return <ArchaeologicalCultureSection {...sectionProps} />;
        case 'language':
            return <LanguageSection {...sectionProps} />;
        case 'religious_text':
            return <ReligiousTextSection {...sectionProps} />;
        case 'legal_code':
            return <LegalCodeSection {...sectionProps} />;
        case 'religious_movement':
            return <ReligiousMovementSection {...sectionProps} />;
        case 'technology':
            return <TechnologySection {...sectionProps} />;
        default:
            return null;
    }
}

// ─── Main EntityForm ─────────────────────────────────────────────────────────

export default function EntityForm({
    data,
    errors,
    processing,
    options,
    onChange,
    onSubmit,
    submitLabel = 'Save',
    onCancel,
}: Props) {
    const entityType = (data.entity_type as EntityType | '') ?? '';

    // When entity_type changes, auto-derive entity_group
    function handleTypeChange(value: string) {
        const typeOption = options.types.find((t) => t.value === value);
        onChange('entity_type', value);

        if (typeOption) {
            onChange('entity_group', typeOption.group as EntityGroup);
        }
    }

    return (
        <form onSubmit={onSubmit} className="space-y-8">
            {/* ── Identity ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                    <FieldWrapper
                        label="Name"
                        htmlFor="name"
                        error={errors.name}
                    >
                        <Input
                            id="name"
                            value={data.name}
                            onChange={(e) => onChange('name', e.target.value)}
                            placeholder="Entity name"
                            required
                        />
                    </FieldWrapper>
                </div>

                <FieldWrapper
                    label="Entity Type"
                    htmlFor="entity_type"
                    error={errors.entity_type}
                >
                    <EnumSelect
                        id="entity_type"
                        value={data.entity_type}
                        onChange={handleTypeChange}
                        options={options.types}
                        placeholder="Select entity type"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Group"
                    htmlFor="entity_group"
                    error={errors.entity_group}
                >
                    <Input
                        id="entity_group"
                        value={
                            data.entity_group
                                ? labelFromValue(data.entity_group)
                                : ''
                        }
                        readOnly
                        className="cursor-default bg-muted text-muted-foreground"
                        placeholder="Derived from type"
                    />
                </FieldWrapper>

                <div className="sm:col-span-2">
                    <FieldWrapper
                        label="Summary"
                        htmlFor="summary"
                        error={errors.summary}
                    >
                        <Textarea
                            id="summary"
                            value={data.summary}
                            onChange={(e) =>
                                onChange('summary', e.target.value)
                            }
                            placeholder="Short description of this entity"
                            rows={3}
                        />
                    </FieldWrapper>
                </div>

                <div className="sm:col-span-2">
                    <FieldWrapper
                        label="Significance"
                        htmlFor="significance"
                        error={errors.significance}
                    >
                        <Textarea
                            id="significance"
                            value={data.significance}
                            onChange={(e) =>
                                onChange('significance', e.target.value)
                            }
                            placeholder="Why is this entity historically significant?"
                            rows={2}
                        />
                    </FieldWrapper>
                </div>
            </div>

            {/* ── Temporal ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <SectionHeading>Temporal</SectionHeading>

                <FieldWrapper
                    label="Start Year"
                    htmlFor="temporal_start"
                    error={errors.temporal_start}
                >
                    <Input
                        id="temporal_start"
                        value={data.temporal_start}
                        onChange={(e) =>
                            onChange('temporal_start', e.target.value)
                        }
                        placeholder="e.g. -500 or 1453"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="End Year"
                    htmlFor="temporal_end"
                    error={errors.temporal_end}
                >
                    <Input
                        id="temporal_end"
                        value={data.temporal_end}
                        onChange={(e) =>
                            onChange('temporal_end', e.target.value)
                        }
                        placeholder="e.g. -31 or 1492"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Raw Date (from source)"
                    htmlFor="date_raw"
                    error={errors.date_raw}
                >
                    <Input
                        id="date_raw"
                        value={data.date_raw}
                        onChange={(e) => onChange('date_raw', e.target.value)}
                        placeholder='e.g. "circa 500 BCE"'
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Date Resolution Method"
                    htmlFor="date_method"
                    error={errors.date_method}
                >
                    <EnumSelect
                        id="date_method"
                        value={data.date_method}
                        onChange={(v) => onChange('date_method', v)}
                        options={options.dateMethods}
                        placeholder="Select method"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Date Confidence"
                    htmlFor="date_confidence"
                    error={errors.date_confidence}
                >
                    <EnumSelect
                        id="date_confidence"
                        value={data.date_confidence}
                        onChange={(v) => onChange('date_confidence', v)}
                        options={options.confidences}
                        placeholder="Select confidence"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Duration Type"
                    htmlFor="duration_type"
                    error={errors.duration_type}
                >
                    <EnumSelect
                        id="duration_type"
                        value={data.duration_type}
                        onChange={(v) => onChange('duration_type', v)}
                        options={options.durationTypes}
                        placeholder="Select duration type"
                    />
                </FieldWrapper>
            </div>

            {/* ── Location ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <SectionHeading>Location</SectionHeading>

                <div className="sm:col-span-2">
                    <FieldWrapper
                        label="Location Name"
                        htmlFor="location_name"
                        error={errors.location_name}
                    >
                        <Input
                            id="location_name"
                            value={data.location_name}
                            onChange={(e) =>
                                onChange('location_name', e.target.value)
                            }
                            placeholder="e.g. Northern Mesopotamia"
                        />
                    </FieldWrapper>
                </div>

                <FieldWrapper
                    label="Location Confidence"
                    htmlFor="location_confidence"
                    error={errors.location_confidence}
                >
                    <EnumSelect
                        id="location_confidence"
                        value={data.location_confidence}
                        onChange={(v) => onChange('location_confidence', v)}
                        options={options.confidences}
                        placeholder="Select confidence"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Location Resolution Method"
                    htmlFor="location_method"
                    error={errors.location_method}
                >
                    <EnumSelect
                        id="location_method"
                        value={data.location_method}
                        onChange={(v) => onChange('location_method', v)}
                        options={options.locationMethods}
                        placeholder="Select method"
                    />
                </FieldWrapper>
            </div>

            {/* ── Hierarchy ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <SectionHeading>Hierarchy</SectionHeading>

                <FieldWrapper
                    label="Parent Entity ID"
                    htmlFor="parent_entity_id"
                    error={errors.parent_entity_id}
                >
                    <Input
                        id="parent_entity_id"
                        value={data.parent_entity_id}
                        onChange={(e) =>
                            onChange('parent_entity_id', e.target.value)
                        }
                        placeholder="UUID of strict parent entity"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Successor Entity ID"
                    htmlFor="successor_entity_id"
                    error={errors.successor_entity_id}
                >
                    <Input
                        id="successor_entity_id"
                        value={data.successor_entity_id}
                        onChange={(e) =>
                            onChange('successor_entity_id', e.target.value)
                        }
                        placeholder="UUID of direct successor entity"
                    />
                </FieldWrapper>
            </div>

            {/* ── Type-specific ── */}
            {entityType && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <TypeSpecificSection
                        entityType={entityType}
                        data={data}
                        errors={errors}
                        onChange={onChange}
                    />
                </div>
            )}

            {/* ── Metadata ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <SectionHeading>Metadata</SectionHeading>

                <FieldWrapper
                    label="Tags (comma-separated)"
                    htmlFor="tags"
                    error={errors.tags}
                >
                    <Input
                        id="tags"
                        value={data.tags}
                        onChange={(e) => onChange('tags', e.target.value)}
                        placeholder="e.g. rome, republic, war"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Alternative Names (comma-separated)"
                    htmlFor="alternative_names"
                    error={errors.alternative_names}
                >
                    <Input
                        id="alternative_names"
                        value={data.alternative_names}
                        onChange={(e) =>
                            onChange('alternative_names', e.target.value)
                        }
                        placeholder="e.g. SPQR, Roman Republic"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Impact Score (0–100)"
                    htmlFor="impact_score"
                    error={errors.impact_score}
                >
                    <Input
                        id="impact_score"
                        type="number"
                        min={0}
                        max={100}
                        value={data.impact_score}
                        onChange={(e) =>
                            onChange('impact_score', e.target.value)
                        }
                        placeholder="e.g. 75"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Wikidata ID"
                    htmlFor="wikidata_id"
                    error={errors.wikidata_id}
                >
                    <Input
                        id="wikidata_id"
                        value={data.wikidata_id}
                        onChange={(e) =>
                            onChange('wikidata_id', e.target.value)
                        }
                        placeholder="e.g. Q1234"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Icon Class"
                    htmlFor="icon_class"
                    error={errors.icon_class}
                >
                    <EnumSelect
                        id="icon_class"
                        value={data.icon_class}
                        onChange={(v) => onChange('icon_class', v)}
                        options={options.iconClasses}
                        placeholder="Select icon"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Entity Color (#rrggbb)"
                    htmlFor="entity_color"
                    error={errors.entity_color}
                >
                    <Input
                        id="entity_color"
                        value={data.entity_color}
                        onChange={(e) =>
                            onChange('entity_color', e.target.value)
                        }
                        placeholder="#3b82f6"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Display Priority (0–100)"
                    htmlFor="display_priority"
                    error={errors.display_priority}
                >
                    <Input
                        id="display_priority"
                        type="number"
                        min={0}
                        max={100}
                        value={data.display_priority}
                        onChange={(e) =>
                            onChange('display_priority', e.target.value)
                        }
                        placeholder="e.g. 50"
                    />
                </FieldWrapper>
            </div>

            {/* ── Verification ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <SectionHeading>Verification</SectionHeading>

                <FieldWrapper
                    label="Verification Status"
                    htmlFor="verification_status"
                    error={errors.verification_status}
                >
                    <EnumSelect
                        id="verification_status"
                        value={data.verification_status}
                        onChange={(v) => onChange('verification_status', v)}
                        options={options.statuses}
                        placeholder="Select status"
                    />
                </FieldWrapper>

                <FieldWrapper
                    label="Overall Confidence"
                    htmlFor="confidence"
                    error={errors.confidence}
                >
                    <EnumSelect
                        id="confidence"
                        value={data.confidence}
                        onChange={(v) => onChange('confidence', v)}
                        options={options.confidences}
                        placeholder="Select confidence"
                    />
                </FieldWrapper>

                <div className="sm:col-span-2">
                    <FieldWrapper
                        label="Confidence Notes"
                        htmlFor="confidence_notes"
                        error={errors.confidence_notes}
                    >
                        <Textarea
                            id="confidence_notes"
                            value={data.confidence_notes}
                            onChange={(e) =>
                                onChange('confidence_notes', e.target.value)
                            }
                            placeholder="Any caveats about date or location confidence"
                            rows={2}
                        />
                    </FieldWrapper>
                </div>
            </div>

            {/* ── Actions ── */}
            <div className="flex items-center gap-3 pt-2">
                <Button type="submit" disabled={processing}>
                    {processing ? 'Saving…' : submitLabel}
                </Button>
                {onCancel && (
                    <Button type="button" variant="outline" onClick={onCancel}>
                        Cancel
                    </Button>
                )}
            </div>
        </form>
    );
}
