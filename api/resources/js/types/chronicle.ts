export type ChronicleStatus = 'draft' | 'published' | 'archived';

export type SourceType = 'video_transcript' | 'article' | 'book_excerpt' | 'manual';

export type ChronicleEntryRole = 'participant' | 'mentioned' | 'location' | 'outcome';

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

export type ChronicleEntry = {
    entry_id: string;
    sequence_order: number;
    timestamp: string | null;
    narrative_text: string;
    notes: string | null;
    source_evidence: string | null;
    primary_relationship: Record<string, unknown> | null;
    secondary_entities: ChronicleEntrySecondaryEntity[] | null;
};

export type ChronicleDetail = {
    chronicle_id: string;
    title: string;
    slug: string;
    source_type: SourceType | null;
    source_reference: string | null;
    status: ChronicleStatus | null;
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

export type ChronicleEntryFormData = {
    entry_id?: string;
    sequence_order: number;
    narrative_text: string;
    notes: string | null;
    source_evidence: string | null;
    primary_relationship_id: string | null;
    secondary_entity_ids: string[];
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
