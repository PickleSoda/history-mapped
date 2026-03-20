export type EntityGroup = 'POLITY' | 'PLACE' | 'EVENT' | 'ECONOMY' | 'CULTURE';

export type EntityType =
    // Polity
    | 'political_entity'
    | 'dynasty'
    | 'person'
    | 'military_unit'
    | 'diplomatic_relationship'
    | 'social_class'
    // Place
    | 'city'
    | 'infrastructure_monument'
    | 'extraction_infra'
    | 'educational_institution'
    // Event
    | 'event_war'
    | 'event_battle'
    | 'event_treaty'
    | 'event_rebellion'
    | 'event_natural_disaster'
    | 'event_tech_adoption'
    | 'event_legal_reform'
    | 'migration'
    | 'epidemic_disease'
    // Economy
    | 'trade_route'
    | 'natural_resource'
    | 'currency_monetary_system'
    // Culture
    | 'cultural_work'
    | 'intellectual_movement'
    | 'archaeological_culture'
    | 'language'
    | 'religious_text'
    | 'legal_code'
    | 'religious_movement'
    | 'technology';

export type VerificationStatus =
    | 'pipeline_draft'
    | 'auto_validated'
    | 'needs_review'
    | 'in_review'
    | 'human_verified'
    | 'expert_verified'
    | 'flagged'
    | 'rejected'
    | 'merged';

export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'unresolved';

export type EntitySummary = {
    id: string;
    name: string;
    entity_type: EntityType | null;
    entity_group: EntityGroup | null;
    summary: string | null;
    impact_score: number | null;
    temporal_start: number | null;
    temporal_end: number | null;
    temporal_display_range: string | null;
    era_label: string | null;
    location_name: string | null;
    verification_status: VerificationStatus | null;
    confidence: ConfidenceLevel | null;
    created_at: string | null;
};

/**
 * Full entity detail shape — used by show, edit, and create pages.
 */
export type EntityDetail = {
    id: string;
    name: string;
    entity_type: EntityType | null;
    entity_group: EntityGroup | null;
    summary: string | null;
    significance: string | null;
    impact_score: number | null;
    wikidata_id: string | null;
    temporal_start: string | null;
    temporal_end: string | null;
    date_raw: string | null;
    date_method: string | null;
    date_confidence: ConfidenceLevel | null;
    duration_type: string | null;
    temporal_display_range: string | null;
    era_label: string | null;
    location_name: string | null;
    location_confidence: ConfidenceLevel | null;
    location_method: string | null;
    parent_entity_id: string | null;
    successor_entity_id: string | null;
    verification_status: VerificationStatus | null;
    confidence: ConfidenceLevel | null;
    confidence_notes: string | null;
    display_priority: number | null;
    icon_class: string | null;
    entity_color: string | null;
    tags: string[];
    alternative_names: string[];
    /** Type-specific JSONB attributes */
    attributes: Record<string, unknown>;
    /** Point/line geometry as GeoJSON (maps to PostGIS geom column) */
    geojson: Record<string, unknown> | null;
    /** Territory/area geometry as GeoJSON (maps to PostGIS territory_geom column) */
    territory_geojson: Record<string, unknown> | null;
    created_at: string | null;
    updated_at: string | null;
};

/** A generic value+label pair used in Select dropdowns. */
export type FilterOption = {
    value: string;
    label: string;
};

/** EntityType option also carries the group for auto-deriving entity_group. */
export type EntityTypeOption = FilterOption & { group: EntityGroup };

export type EntityFilters = {
    search: string;
    type: string;
    group: string;
    status: string;
    confidence: string;
    date_from: string;
    date_to: string;
    sort: string;
    per_page: number;
};

export type EntityFilterOptions = {
    types: FilterOption[];
    groups: FilterOption[];
    statuses: FilterOption[];
    confidences: FilterOption[];
};

/**
 * Enum option lists passed to create/edit form pages from the controller.
 */
export type EntityFormOptions = {
    types: EntityTypeOption[];
    groups: FilterOption[];
    statuses: FilterOption[];
    confidences: FilterOption[];
    dateMethods: FilterOption[];
    durationTypes: FilterOption[];
    locationMethods: FilterOption[];
    iconClasses: FilterOption[];
};

export type PaginatedData<T> = {
    data: T[];
    current_page: number;
    last_page: number;
    per_page: number;
    total: number;
    from: number | null;
    to: number | null;
};
