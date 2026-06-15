export type ChronicleStatus = 'draft' | 'published' | 'archived';

export type SourceType =
    | 'video_transcript'
    | 'article'
    | 'book_excerpt'
    | 'manual';

export type ChronicleEntryRole =
    | 'participant'
    | 'mentioned'
    | 'location'
    | 'outcome';

export type ChronicleSummary = {
    chronicle_id: string;
    title: string;
    slug: string;
    source_type: SourceType | null;
    status: ChronicleStatus | null;
    entry_count: number;
    created_at: string | null;
    updated_at: string | null;
};

export type ChronicleEntrySecondaryEntity = {
    entity_id: string;
    name: string;
    entity_type: string | null;
    role: ChronicleEntryRole | null;
};

export type ApproximateLocation = { lat: number; lon: number };

export type ChronicleEntryPrimaryRelationship = {
    relationship_id: string;
    relationship_type: string | null;
    source_name: string | null;
    target_name: string | null;
};

export type ChronicleEntry = {
    entry_id: string;
    sequence_order: number;
    timestamp: string | null;
    start_year: number | null;
    end_year: number | null;
    impact_score: number | null;
    approximate_location: ApproximateLocation | null;
    narrative_text: string;
    notes: string | null;
    source_evidence: string | null;
    primary_relationship_id: string | null;
    primary_relationship: ChronicleEntryPrimaryRelationship | null;
    secondary_entities: ChronicleEntrySecondaryEntity[] | null;
};

export type ChronicleDetail = {
    chronicle_id: string;
    title: string;
    slug: string;
    source_type: SourceType | null;
    source_reference: string | null;
    status: ChronicleStatus | null;
    start_year: number | null;
    end_year: number | null;
    impact_score: number | null;
    approximate_location: ApproximateLocation | null;
    metadata: Record<string, unknown>;
    entry_count: number;
    entries: ChronicleEntry[] | null;
    created_at: string | null;
    updated_at: string | null;
};

export type PaginatedChronicles = {
    data: ChronicleSummary[];
    current_page: number;
    last_page: number;
    per_page: number;
    total: number;
    from: number | null;
    to: number | null;
};

export type ChronicleFilters = {
    search: string;
    status: string;
    per_page: number;
    page: number;
};

export type ChronicleEntrySecondaryForm = {
    entity_id: string;
    name: string;
    role: string;
};

export type ChronicleEntryNewRelationship = {
    source_entity_id: string;
    target_entity_id: string;
    relationship_type: string;
};

export type ChronicleEntryFormData = {
    entry_id?: string;
    sequence_order: number;
    narrative_text: string;
    notes: string | null;
    source_evidence: string | null;
    primary_relationship_id: string | null;
    primary_relationship_label: string | null;
    new_relationship: ChronicleEntryNewRelationship | null;
    secondary_entities: ChronicleEntrySecondaryForm[];
};

export type ChronicleFormData = {
    title: string;
    slug: string;
    source_type: string;
    source_reference: string;
    status: string;
    metadata: string;
    entries: ChronicleEntryFormData[];
};
