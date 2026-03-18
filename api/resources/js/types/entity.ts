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

export type EntityFilters = {
    search: string;
    group: string;
    status: string;
    confidence: string;
    sort: string;
    per_page: number;
};

export type FilterOption = {
    value: string;
    label: string;
};

export type EntityFilterOptions = {
    groups: FilterOption[];
    statuses: FilterOption[];
    confidences: FilterOption[];
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
