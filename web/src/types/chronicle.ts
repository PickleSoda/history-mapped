export interface Chronicle {
    chronicle_id: string;
    title: string;
    slug: string;
    source_type: string | null;
    source_reference: string | null;
    status: string;
    start_year: number | null;
    end_year: number | null;
    impact_score: number | null;
    approximate_location: { lat: number; lng: number } | null;
    metadata: Record<string, any> | null;
    created_by: string | null;
    created_at: string;
    updated_at: string;
    entries?: ChronicleEntry[];
}

export interface ChronicleEntry {
    entry_id: string;
    chronicle_id: string;
    sequence_order: number;
    start_year: number | null;
    end_year: number | null;
    impact_score: number | null;
    approximate_location: { lat: number; lng: number } | null;
    primary_relationship_id: string | null;
    narrative_text: string | null;
    notes: string | null;
    source_evidence: string | null;
    generated_by: string | null;
    created_at: string;
    updated_at: string;
}