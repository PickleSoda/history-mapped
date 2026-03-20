export type GeographicRegion = {
    region_id: number;
    name: string;
    depth_level: number;
    parent_name: string | null;
    modern_countries: string[] | null;
    batch_priority: number;
    sort_order: number | null;
};

export type HistoricalPeriod = {
    period_id: number;
    name: string;
    depth_level: number;
    parent_name: string | null;
    start_date: string;
    end_date: string;
    geographic_scope: string;
    periodization_scheme: string;
    region_name: string | null;
    color_hex: string | null;
    sort_order: number | null;
};

export type HistoriographicalSchool = {
    school_id: number;
    name: string;
    active_from: string | null;
    active_to: string | null;
    interpretive_framework: string;
    geographic_center: string | null;
    sort_order: number | null;
};

export type CalendarSystem = {
    calendar_id: number;
    name: string;
    code: string;
    calendar_type: string;
    epoch_gregorian: string | null;
    still_in_use: boolean;
};

export type EraDateLookup = {
    lookup_id: number;
    search_term: string;
    resolved_start: string;
    resolved_end: string;
    geographic_scope: string | null;
    confidence: string;
    period_name: string | null;
};

export type WritingSystem = {
    system_id: number;
    name: string;
    code: string | null;
    system_type: string;
    direction: string | null;
    origin_date: string | null;
    derived_from_name: string | null;
    still_in_use: boolean;
};

export type ReligiousTradition = {
    tradition_id: number;
    name: string;
    depth_level: number;
    parent_name: string | null;
    tradition_type: string | null;
    origin_date: string | null;
    origin_region: string | null;
    founder: string | null;
    color_hex: string | null;
    sort_order: number | null;
};

export type MeasurementUnit = {
    unit_id: number;
    name: string;
    symbol: string | null;
    measurement_type: string;
    si_equivalent: string | null;
    si_unit: string | null;
    used_by_region: string | null;
    used_by_period: string | null;
    approximate: boolean;
};

export type LanguageFamily = {
    family_id: number;
    name: string;
    depth_level: number;
    parent_name: string | null;
    proto_language: string | null;
    estimated_origin: string | null;
    estimated_homeland: string | null;
    living_languages: number | null;
    status: string | null;
    sort_order: number | null;
};

export type SourceTypeDefinition = {
    definition_id: number;
    enum_name: string;
    enum_value: string;
    description: string;
    default_confidence: string | null;
    requires_corroboration: boolean;
    weight_in_scoring: string | null;
};
