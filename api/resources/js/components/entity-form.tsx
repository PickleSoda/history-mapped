import InputError from '@/components/input-error';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import type { EntityFormOptions, EntityGroup, EntityType } from '@/types';

// ─── Attribute sub-type enums (kept client-side — no backend roundtrip needed) ───

const BATTLE_SUBTYPES = ['pitched_battle', 'siege', 'naval_battle', 'ambush', 'skirmish', 'raid', 'last_stand', 'other'] as const;
const BATTLE_OUTCOMES = ['decisive_victory', 'pyrrhic_victory', 'tactical_victory', 'stalemate', 'defeat', 'inconclusive'] as const;
const WAR_SUBTYPES = ['territorial', 'religious', 'succession', 'civil', 'colonial', 'trade', 'ideological', 'other'] as const;
const TREATY_SUBTYPES = ['peace', 'alliance', 'trade', 'border', 'tribute', 'surrender', 'other'] as const;
const REBELLION_SUBTYPES = ['slave_revolt', 'peasant_revolt', 'separatist', 'coup', 'religious', 'other'] as const;
const DISASTER_SUBTYPES = ['earthquake', 'flood', 'drought', 'volcano', 'tsunami', 'famine', 'other'] as const;
const EPIDEMIC_SUBTYPES = ['plague', 'smallpox', 'cholera', 'typhus', 'malaria', 'influenza', 'other'] as const;
const EPIDEMIC_SEVERITIES = ['local', 'regional', 'pandemic'] as const;
const PERSON_ROLES = ['ruler', 'regent', 'heir', 'consort', 'general', 'admiral', 'diplomat', 'governor', 'religious_leader', 'prophet', 'philosopher', 'scientist', 'artist', 'architect', 'poet', 'historian', 'lawgiver', 'rebel_leader', 'merchant', 'explorer', 'spy', 'slave', 'other'] as const;
const GENDERS = ['male', 'female', 'nonbinary', 'unknown'] as const;
const GOVERNMENT_TYPES = ['absolute_monarchy', 'constitutional_monarchy', 'elective_monarchy', 'oligarchy', 'aristocratic_republic', 'democratic_republic', 'theocracy', 'military_dictatorship', 'tribal_chieftainship', 'feudal', 'bureaucratic_centralized', 'colonial_administration', 'communist_state', 'fascist_state', 'anarchy', 'diarchy', 'federal', 'confederal', 'other'] as const;
const SUCCESSION_TYPES = ['hereditary', 'elective', 'theocratic', 'military', 'meritocratic', 'other'] as const;
const DIPLOMATIC_STATUSES = ['alliance', 'rivalry', 'tributary', 'protectorate', 'neutral', 'hostile', 'vassal'] as const;
const MILITARY_UNIT_SUBTYPES = ['infantry', 'cavalry', 'navy', 'siege', 'mixed', 'mercenary', 'guard', 'other'] as const;
const MILITARY_COMPOSITIONS = ['professional', 'conscript', 'mercenary', 'tribal', 'mixed'] as const;
const TRADE_ROUTE_SUBTYPES = ['land', 'maritime', 'river', 'mixed'] as const;
const RESOURCE_CATEGORIES = ['mineral', 'agricultural', 'timber', 'water', 'animal', 'energy', 'other'] as const;
const RESOURCE_RENEWABILITIES = ['renewable', 'non_renewable', 'semi_renewable'] as const;
const RESOURCE_STRATEGIC_VALUES = ['critical', 'high', 'medium', 'low'] as const;
const CULTURAL_WORK_SUBTYPES = ['text', 'architecture', 'sculpture', 'painting', 'music', 'theatre', 'other'] as const;
const INTELLECTUAL_MOVEMENT_SUBTYPES = ['philosophy', 'science', 'theology', 'literature', 'art', 'political', 'other'] as const;
const LANGUAGE_STATUSES = ['living', 'extinct', 'reconstructed', 'liturgical'] as const;
const LANGUAGE_ROLES = ['official', 'trade', 'liturgical', 'vernacular', 'other'] as const;
const RELIGIOUS_MOVEMENT_SUBTYPES = ['reform', 'schism', 'revival', 'syncretic', 'mystical', 'other'] as const;
const TECH_DOMAINS = ['agriculture', 'metallurgy', 'construction', 'navigation', 'military', 'medicine', 'communication', 'mathematics', 'astronomy', 'other'] as const;
const MIGRATION_SUBTYPES = ['forced', 'voluntary', 'nomadic', 'colonization', 'diaspora', 'other'] as const;

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
    onChange: <K extends keyof EntityFormData>(field: K, value: EntityFormData[K]) => void;
    onSubmit: (e: React.FormEvent) => void;
    submitLabel?: string;
    onCancel?: () => void;
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function labelFromValue(value: string): string {
    return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function FieldWrapper({ label, htmlFor, error, children }: { label: string; htmlFor: string; error?: string; children: React.ReactNode }) {
    return (
        <div className="grid gap-1.5">
            <Label htmlFor={htmlFor}>{label}</Label>
            {children}
            {error && <InputError message={error} />}
        </div>
    );
}

function EnumSelect({ id, value, onChange, options, placeholder }: { id: string; value: string; onChange: (v: string) => void; options: readonly string[] | { value: string; label: string }[]; placeholder: string }) {
    const normalised: { value: string; label: string }[] = (options as (string | { value: string; label: string })[]).map((o) =>
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
            <Separator className="mb-4 mt-2" />
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{children}</h3>
        </div>
    );
}

// ─── Type-specific attribute sections ────────────────────────────────────────

function PoliticalEntitySection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Political Entity Details</SectionHeading>
            <FieldWrapper label="Government Type" htmlFor="attr_government_type" error={errors['attributes.government_type']}>
                <EnumSelect id="attr_government_type" value={data.attr_government_type ?? ''} onChange={(v) => onChange('attr_government_type', v)} options={GOVERNMENT_TYPES} placeholder="Select government type" />
            </FieldWrapper>
            <FieldWrapper label="Succession Type" htmlFor="attr_succession_type" error={errors['attributes.succession_type']}>
                <EnumSelect id="attr_succession_type" value={data.attr_succession_type ?? ''} onChange={(v) => onChange('attr_succession_type', v)} options={SUCCESSION_TYPES} placeholder="Select succession type" />
            </FieldWrapper>
            <FieldWrapper label="Diplomatic Status" htmlFor="attr_diplomatic_status" error={errors['attributes.diplomatic_status']}>
                <EnumSelect id="attr_diplomatic_status" value={data.attr_diplomatic_status ?? ''} onChange={(v) => onChange('attr_diplomatic_status', v)} options={DIPLOMATIC_STATUSES} placeholder="Select diplomatic status" />
            </FieldWrapper>
        </>
    );
}

function PersonSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Person Details</SectionHeading>
            <FieldWrapper label="Role" htmlFor="attr_role" error={errors['attributes.role']}>
                <EnumSelect id="attr_role" value={data.attr_role ?? ''} onChange={(v) => onChange('attr_role', v)} options={PERSON_ROLES} placeholder="Select role" />
            </FieldWrapper>
            <FieldWrapper label="Gender" htmlFor="attr_gender" error={errors['attributes.gender']}>
                <EnumSelect id="attr_gender" value={data.attr_gender ?? ''} onChange={(v) => onChange('attr_gender', v)} options={GENDERS} placeholder="Select gender" />
            </FieldWrapper>
            <FieldWrapper label="Birth Year" htmlFor="attr_birth_year" error={errors['attributes.birth_year']}>
                <Input id="attr_birth_year" value={data.attr_birth_year ?? ''} onChange={(e) => onChange('attr_birth_year', e.target.value)} placeholder="e.g. -100 or 44" />
            </FieldWrapper>
            <FieldWrapper label="Death Year" htmlFor="attr_death_year" error={errors['attributes.death_year']}>
                <Input id="attr_death_year" value={data.attr_death_year ?? ''} onChange={(e) => onChange('attr_death_year', e.target.value)} placeholder="e.g. -100 or 44" />
            </FieldWrapper>
        </>
    );
}

function MilitaryUnitSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Military Unit Details</SectionHeading>
            <FieldWrapper label="Unit Type" htmlFor="attr_unit_type" error={errors['attributes.unit_type']}>
                <EnumSelect id="attr_unit_type" value={data.attr_unit_type ?? ''} onChange={(v) => onChange('attr_unit_type', v)} options={MILITARY_UNIT_SUBTYPES} placeholder="Select unit type" />
            </FieldWrapper>
            <FieldWrapper label="Composition" htmlFor="attr_composition" error={errors['attributes.composition']}>
                <EnumSelect id="attr_composition" value={data.attr_composition ?? ''} onChange={(v) => onChange('attr_composition', v)} options={MILITARY_COMPOSITIONS} placeholder="Select composition" />
            </FieldWrapper>
            <FieldWrapper label="Estimated Size" htmlFor="attr_size" error={errors['attributes.size']}>
                <Input id="attr_size" value={data.attr_size ?? ''} onChange={(e) => onChange('attr_size', e.target.value)} placeholder="e.g. 10000" />
            </FieldWrapper>
        </>
    );
}

function EventBattleSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Battle Details</SectionHeading>
            <FieldWrapper label="Battle Type" htmlFor="attr_battle_type" error={errors['attributes.battle_type']}>
                <EnumSelect id="attr_battle_type" value={data.attr_battle_type ?? ''} onChange={(v) => onChange('attr_battle_type', v)} options={BATTLE_SUBTYPES} placeholder="Select battle type" />
            </FieldWrapper>
            <FieldWrapper label="Outcome" htmlFor="attr_outcome" error={errors['attributes.outcome']}>
                <EnumSelect id="attr_outcome" value={data.attr_outcome ?? ''} onChange={(v) => onChange('attr_outcome', v)} options={BATTLE_OUTCOMES} placeholder="Select outcome" />
            </FieldWrapper>
            <FieldWrapper label="Attacker" htmlFor="attr_attacker" error={errors['attributes.attacker']}>
                <Input id="attr_attacker" value={data.attr_attacker ?? ''} onChange={(e) => onChange('attr_attacker', e.target.value)} placeholder="Name of attacker" />
            </FieldWrapper>
            <FieldWrapper label="Defender" htmlFor="attr_defender" error={errors['attributes.defender']}>
                <Input id="attr_defender" value={data.attr_defender ?? ''} onChange={(e) => onChange('attr_defender', e.target.value)} placeholder="Name of defender" />
            </FieldWrapper>
        </>
    );
}

function EventWarSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>War Details</SectionHeading>
            <FieldWrapper label="War Type" htmlFor="attr_war_type" error={errors['attributes.war_type']}>
                <EnumSelect id="attr_war_type" value={data.attr_war_type ?? ''} onChange={(v) => onChange('attr_war_type', v)} options={WAR_SUBTYPES} placeholder="Select war type" />
            </FieldWrapper>
        </>
    );
}

function EventTreatySection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Treaty Details</SectionHeading>
            <FieldWrapper label="Treaty Type" htmlFor="attr_treaty_type" error={errors['attributes.treaty_type']}>
                <EnumSelect id="attr_treaty_type" value={data.attr_treaty_type ?? ''} onChange={(v) => onChange('attr_treaty_type', v)} options={TREATY_SUBTYPES} placeholder="Select treaty type" />
            </FieldWrapper>
            <FieldWrapper label="Parties" htmlFor="attr_parties" error={errors['attributes.parties']}>
                <Input id="attr_parties" value={data.attr_parties ?? ''} onChange={(e) => onChange('attr_parties', e.target.value)} placeholder="Comma-separated parties" />
            </FieldWrapper>
        </>
    );
}

function EventRebellionSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Rebellion Details</SectionHeading>
            <FieldWrapper label="Rebellion Type" htmlFor="attr_rebellion_type" error={errors['attributes.rebellion_type']}>
                <EnumSelect id="attr_rebellion_type" value={data.attr_rebellion_type ?? ''} onChange={(v) => onChange('attr_rebellion_type', v)} options={REBELLION_SUBTYPES} placeholder="Select rebellion type" />
            </FieldWrapper>
        </>
    );
}

function EpidemicSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Epidemic / Disease Details</SectionHeading>
            <FieldWrapper label="Disease Type" htmlFor="attr_disease_type" error={errors['attributes.disease_type']}>
                <EnumSelect id="attr_disease_type" value={data.attr_disease_type ?? ''} onChange={(v) => onChange('attr_disease_type', v)} options={EPIDEMIC_SUBTYPES} placeholder="Select disease type" />
            </FieldWrapper>
            <FieldWrapper label="Severity" htmlFor="attr_severity" error={errors['attributes.severity']}>
                <EnumSelect id="attr_severity" value={data.attr_severity ?? ''} onChange={(v) => onChange('attr_severity', v)} options={EPIDEMIC_SEVERITIES} placeholder="Select severity" />
            </FieldWrapper>
            <FieldWrapper label="Estimated Deaths" htmlFor="attr_estimated_deaths" error={errors['attributes.estimated_deaths']}>
                <Input id="attr_estimated_deaths" value={data.attr_estimated_deaths ?? ''} onChange={(e) => onChange('attr_estimated_deaths', e.target.value)} placeholder="e.g. 50000000" />
            </FieldWrapper>
        </>
    );
}

function TradeRouteSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Trade Route Details</SectionHeading>
            <FieldWrapper label="Route Type" htmlFor="attr_route_type" error={errors['attributes.route_type']}>
                <EnumSelect id="attr_route_type" value={data.attr_route_type ?? ''} onChange={(v) => onChange('attr_route_type', v)} options={TRADE_ROUTE_SUBTYPES} placeholder="Select route type" />
            </FieldWrapper>
            <FieldWrapper label="Key Commodities" htmlFor="attr_commodities" error={errors['attributes.commodities']}>
                <Input id="attr_commodities" value={data.attr_commodities ?? ''} onChange={(e) => onChange('attr_commodities', e.target.value)} placeholder="Comma-separated commodities" />
            </FieldWrapper>
        </>
    );
}

function NaturalResourceSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Natural Resource Details</SectionHeading>
            <FieldWrapper label="Resource Category" htmlFor="attr_resource_category" error={errors['attributes.resource_category']}>
                <EnumSelect id="attr_resource_category" value={data.attr_resource_category ?? ''} onChange={(v) => onChange('attr_resource_category', v)} options={RESOURCE_CATEGORIES} placeholder="Select category" />
            </FieldWrapper>
            <FieldWrapper label="Renewability" htmlFor="attr_renewability" error={errors['attributes.renewability']}>
                <EnumSelect id="attr_renewability" value={data.attr_renewability ?? ''} onChange={(v) => onChange('attr_renewability', v)} options={RESOURCE_RENEWABILITIES} placeholder="Select renewability" />
            </FieldWrapper>
            <FieldWrapper label="Strategic Value" htmlFor="attr_strategic_value" error={errors['attributes.strategic_value']}>
                <EnumSelect id="attr_strategic_value" value={data.attr_strategic_value ?? ''} onChange={(v) => onChange('attr_strategic_value', v)} options={RESOURCE_STRATEGIC_VALUES} placeholder="Select strategic value" />
            </FieldWrapper>
        </>
    );
}

function CulturalWorkSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Cultural Work Details</SectionHeading>
            <FieldWrapper label="Work Type" htmlFor="attr_work_type" error={errors['attributes.work_type']}>
                <EnumSelect id="attr_work_type" value={data.attr_work_type ?? ''} onChange={(v) => onChange('attr_work_type', v)} options={CULTURAL_WORK_SUBTYPES} placeholder="Select work type" />
            </FieldWrapper>
            <FieldWrapper label="Creator / Author" htmlFor="attr_creator" error={errors['attributes.creator']}>
                <Input id="attr_creator" value={data.attr_creator ?? ''} onChange={(e) => onChange('attr_creator', e.target.value)} placeholder="Name of creator or author" />
            </FieldWrapper>
        </>
    );
}

function LanguageSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Language Details</SectionHeading>
            <FieldWrapper label="Language Status" htmlFor="attr_language_status" error={errors['attributes.language_status']}>
                <EnumSelect id="attr_language_status" value={data.attr_language_status ?? ''} onChange={(v) => onChange('attr_language_status', v)} options={LANGUAGE_STATUSES} placeholder="Select status" />
            </FieldWrapper>
            <FieldWrapper label="Language Role" htmlFor="attr_language_role" error={errors['attributes.language_role']}>
                <EnumSelect id="attr_language_role" value={data.attr_language_role ?? ''} onChange={(v) => onChange('attr_language_role', v)} options={LANGUAGE_ROLES} placeholder="Select role" />
            </FieldWrapper>
        </>
    );
}

function ReligiousMovementSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Religious Movement Details</SectionHeading>
            <FieldWrapper label="Movement Type" htmlFor="attr_movement_type" error={errors['attributes.movement_type']}>
                <EnumSelect id="attr_movement_type" value={data.attr_movement_type ?? ''} onChange={(v) => onChange('attr_movement_type', v)} options={RELIGIOUS_MOVEMENT_SUBTYPES} placeholder="Select movement type" />
            </FieldWrapper>
        </>
    );
}

function TechnologySection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Technology Details</SectionHeading>
            <FieldWrapper label="Domain" htmlFor="attr_domain" error={errors['attributes.domain']}>
                <EnumSelect id="attr_domain" value={data.attr_domain ?? ''} onChange={(v) => onChange('attr_domain', v)} options={TECH_DOMAINS} placeholder="Select domain" />
            </FieldWrapper>
        </>
    );
}

function MigrationSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Migration Details</SectionHeading>
            <FieldWrapper label="Migration Type" htmlFor="attr_migration_type" error={errors['attributes.migration_type']}>
                <EnumSelect id="attr_migration_type" value={data.attr_migration_type ?? ''} onChange={(v) => onChange('attr_migration_type', v)} options={MIGRATION_SUBTYPES} placeholder="Select migration type" />
            </FieldWrapper>
        </>
    );
}

function DisasterSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Natural Disaster Details</SectionHeading>
            <FieldWrapper label="Disaster Type" htmlFor="attr_disaster_type" error={errors['attributes.disaster_type']}>
                <EnumSelect id="attr_disaster_type" value={data.attr_disaster_type ?? ''} onChange={(v) => onChange('attr_disaster_type', v)} options={DISASTER_SUBTYPES} placeholder="Select disaster type" />
            </FieldWrapper>
        </>
    );
}

function IntellectualMovementSection({ data, errors, onChange }: Pick<Props, 'data' | 'errors' | 'onChange'>) {
    return (
        <>
            <SectionHeading>Intellectual Movement Details</SectionHeading>
            <FieldWrapper label="Movement Type" htmlFor="attr_intellectual_type" error={errors['attributes.intellectual_type']}>
                <EnumSelect id="attr_intellectual_type" value={data.attr_intellectual_type ?? ''} onChange={(v) => onChange('attr_intellectual_type', v)} options={INTELLECTUAL_MOVEMENT_SUBTYPES} placeholder="Select type" />
            </FieldWrapper>
        </>
    );
}

// ─── Type-specific section router ─────────────────────────────────────────────

function TypeSpecificSection({ entityType, data, errors, onChange }: { entityType: EntityType | '' } & Pick<Props, 'data' | 'errors' | 'onChange'>) {
    const sectionProps = { data, errors, onChange };
    switch (entityType) {
        case 'political_entity':
        case 'dynasty':
            return <PoliticalEntitySection {...sectionProps} />;
        case 'person':
            return <PersonSection {...sectionProps} />;
        case 'military_unit':
            return <MilitaryUnitSection {...sectionProps} />;
        case 'event_battle':
            return <EventBattleSection {...sectionProps} />;
        case 'event_war':
            return <EventWarSection {...sectionProps} />;
        case 'event_treaty':
            return <EventTreatySection {...sectionProps} />;
        case 'event_rebellion':
            return <EventRebellionSection {...sectionProps} />;
        case 'epidemic_disease':
            return <EpidemicSection {...sectionProps} />;
        case 'event_natural_disaster':
            return <DisasterSection {...sectionProps} />;
        case 'trade_route':
            return <TradeRouteSection {...sectionProps} />;
        case 'natural_resource':
            return <NaturalResourceSection {...sectionProps} />;
        case 'cultural_work':
            return <CulturalWorkSection {...sectionProps} />;
        case 'language':
            return <LanguageSection {...sectionProps} />;
        case 'religious_movement':
            return <ReligiousMovementSection {...sectionProps} />;
        case 'technology':
            return <TechnologySection {...sectionProps} />;
        case 'migration':
            return <MigrationSection {...sectionProps} />;
        case 'intellectual_movement':
            return <IntellectualMovementSection {...sectionProps} />;
        default:
            return null;
    }
}

// ─── Main EntityForm ─────────────────────────────────────────────────────────

export default function EntityForm({ data, errors, processing, options, onChange, onSubmit, submitLabel = 'Save', onCancel }: Props) {
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
                    <FieldWrapper label="Name" htmlFor="name" error={errors.name}>
                        <Input id="name" value={data.name} onChange={(e) => onChange('name', e.target.value)} placeholder="Entity name" required />
                    </FieldWrapper>
                </div>

                <FieldWrapper label="Entity Type" htmlFor="entity_type" error={errors.entity_type}>
                    <EnumSelect id="entity_type" value={data.entity_type} onChange={handleTypeChange} options={options.types} placeholder="Select entity type" />
                </FieldWrapper>

                <FieldWrapper label="Group" htmlFor="entity_group" error={errors.entity_group}>
                    <Input id="entity_group" value={data.entity_group ? labelFromValue(data.entity_group) : ''} readOnly className="bg-muted text-muted-foreground cursor-default" placeholder="Derived from type" />
                </FieldWrapper>

                <div className="sm:col-span-2">
                    <FieldWrapper label="Summary" htmlFor="summary" error={errors.summary}>
                        <Textarea id="summary" value={data.summary} onChange={(e) => onChange('summary', e.target.value)} placeholder="Short description of this entity" rows={3} />
                    </FieldWrapper>
                </div>

                <div className="sm:col-span-2">
                    <FieldWrapper label="Significance" htmlFor="significance" error={errors.significance}>
                        <Textarea id="significance" value={data.significance} onChange={(e) => onChange('significance', e.target.value)} placeholder="Why is this entity historically significant?" rows={2} />
                    </FieldWrapper>
                </div>
            </div>

            {/* ── Temporal ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <SectionHeading>Temporal</SectionHeading>

                <FieldWrapper label="Start Year" htmlFor="temporal_start" error={errors.temporal_start}>
                    <Input id="temporal_start" value={data.temporal_start} onChange={(e) => onChange('temporal_start', e.target.value)} placeholder="e.g. -500 or 1453" />
                </FieldWrapper>

                <FieldWrapper label="End Year" htmlFor="temporal_end" error={errors.temporal_end}>
                    <Input id="temporal_end" value={data.temporal_end} onChange={(e) => onChange('temporal_end', e.target.value)} placeholder="e.g. -31 or 1492" />
                </FieldWrapper>

                <FieldWrapper label="Raw Date (from source)" htmlFor="date_raw" error={errors.date_raw}>
                    <Input id="date_raw" value={data.date_raw} onChange={(e) => onChange('date_raw', e.target.value)} placeholder='e.g. "circa 500 BCE"' />
                </FieldWrapper>

                <FieldWrapper label="Date Resolution Method" htmlFor="date_method" error={errors.date_method}>
                    <EnumSelect id="date_method" value={data.date_method} onChange={(v) => onChange('date_method', v)} options={options.dateMethods} placeholder="Select method" />
                </FieldWrapper>

                <FieldWrapper label="Date Confidence" htmlFor="date_confidence" error={errors.date_confidence}>
                    <EnumSelect id="date_confidence" value={data.date_confidence} onChange={(v) => onChange('date_confidence', v)} options={options.confidences} placeholder="Select confidence" />
                </FieldWrapper>

                <FieldWrapper label="Duration Type" htmlFor="duration_type" error={errors.duration_type}>
                    <EnumSelect id="duration_type" value={data.duration_type} onChange={(v) => onChange('duration_type', v)} options={options.durationTypes} placeholder="Select duration type" />
                </FieldWrapper>
            </div>

            {/* ── Location ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <SectionHeading>Location</SectionHeading>

                <div className="sm:col-span-2">
                    <FieldWrapper label="Location Name" htmlFor="location_name" error={errors.location_name}>
                        <Input id="location_name" value={data.location_name} onChange={(e) => onChange('location_name', e.target.value)} placeholder="e.g. Northern Mesopotamia" />
                    </FieldWrapper>
                </div>

                <FieldWrapper label="Location Confidence" htmlFor="location_confidence" error={errors.location_confidence}>
                    <EnumSelect id="location_confidence" value={data.location_confidence} onChange={(v) => onChange('location_confidence', v)} options={options.confidences} placeholder="Select confidence" />
                </FieldWrapper>

                <FieldWrapper label="Location Resolution Method" htmlFor="location_method" error={errors.location_method}>
                    <EnumSelect id="location_method" value={data.location_method} onChange={(v) => onChange('location_method', v)} options={options.locationMethods} placeholder="Select method" />
                </FieldWrapper>
            </div>

            {/* ── Type-specific ── */}
            {entityType && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <TypeSpecificSection entityType={entityType} data={data} errors={errors} onChange={onChange} />
                </div>
            )}

            {/* ── Metadata ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <SectionHeading>Metadata</SectionHeading>

                <FieldWrapper label="Tags (comma-separated)" htmlFor="tags" error={errors.tags}>
                    <Input id="tags" value={data.tags} onChange={(e) => onChange('tags', e.target.value)} placeholder="e.g. rome, republic, war" />
                </FieldWrapper>

                <FieldWrapper label="Alternative Names (comma-separated)" htmlFor="alternative_names" error={errors.alternative_names}>
                    <Input id="alternative_names" value={data.alternative_names} onChange={(e) => onChange('alternative_names', e.target.value)} placeholder="e.g. SPQR, Roman Republic" />
                </FieldWrapper>

                <FieldWrapper label="Impact Score (0–100)" htmlFor="impact_score" error={errors.impact_score}>
                    <Input id="impact_score" type="number" min={0} max={100} value={data.impact_score} onChange={(e) => onChange('impact_score', e.target.value)} placeholder="e.g. 75" />
                </FieldWrapper>

                <FieldWrapper label="Wikidata ID" htmlFor="wikidata_id" error={errors.wikidata_id}>
                    <Input id="wikidata_id" value={data.wikidata_id} onChange={(e) => onChange('wikidata_id', e.target.value)} placeholder="e.g. Q1234" />
                </FieldWrapper>

                <FieldWrapper label="Icon Class" htmlFor="icon_class" error={errors.icon_class}>
                    <EnumSelect id="icon_class" value={data.icon_class} onChange={(v) => onChange('icon_class', v)} options={options.iconClasses} placeholder="Select icon" />
                </FieldWrapper>

                <FieldWrapper label="Entity Color (#rrggbb)" htmlFor="entity_color" error={errors.entity_color}>
                    <Input id="entity_color" value={data.entity_color} onChange={(e) => onChange('entity_color', e.target.value)} placeholder="#3b82f6" />
                </FieldWrapper>

                <FieldWrapper label="Display Priority (0–100)" htmlFor="display_priority" error={errors.display_priority}>
                    <Input id="display_priority" type="number" min={0} max={100} value={data.display_priority} onChange={(e) => onChange('display_priority', e.target.value)} placeholder="e.g. 50" />
                </FieldWrapper>
            </div>

            {/* ── Verification ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <SectionHeading>Verification</SectionHeading>

                <FieldWrapper label="Verification Status" htmlFor="verification_status" error={errors.verification_status}>
                    <EnumSelect id="verification_status" value={data.verification_status} onChange={(v) => onChange('verification_status', v)} options={options.statuses} placeholder="Select status" />
                </FieldWrapper>

                <FieldWrapper label="Overall Confidence" htmlFor="confidence" error={errors.confidence}>
                    <EnumSelect id="confidence" value={data.confidence} onChange={(v) => onChange('confidence', v)} options={options.confidences} placeholder="Select confidence" />
                </FieldWrapper>

                <div className="sm:col-span-2">
                    <FieldWrapper label="Confidence Notes" htmlFor="confidence_notes" error={errors.confidence_notes}>
                        <Textarea id="confidence_notes" value={data.confidence_notes} onChange={(e) => onChange('confidence_notes', e.target.value)} placeholder="Any caveats about date or location confidence" rows={2} />
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
