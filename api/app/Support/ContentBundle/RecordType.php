<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\EntityRelationship;
use App\Models\GeometryPeriod;
use Illuminate\Database\Eloquent\Model;

/**
 * The six record files of a bundle. Case values are the file stems.
 */
enum RecordType: string
{
    case Entities = 'entities';
    case Relationships = 'relationships';
    case GeometryPeriods = 'geometry_periods';
    case GeoRefs = 'geo_refs';
    case Chronicles = 'chronicles';
    case ChronicleEntries = 'chronicle_entries';

    public function file(): string
    {
        return $this->value.'.jsonl';
    }

    public static function fromFile(string $file): ?self
    {
        foreach (self::cases() as $case) {
            if ($case->file() === $file) {
                return $case;
            }
        }

        return null;
    }

    public function primaryKey(): string
    {
        return match ($this) {
            self::Entities => 'entity_id',
            self::Relationships => 'relationship_id',
            self::GeometryPeriods => 'geometry_period_id',
            self::GeoRefs => 'geo_ref_id',
            self::Chronicles => 'chronicle_id',
            self::ChronicleEntries => 'entry_id',
        };
    }

    /** @return class-string<Model> */
    public function modelClass(): string
    {
        return match ($this) {
            self::Entities => Entity::class,
            self::Relationships => EntityRelationship::class,
            self::GeometryPeriods => GeometryPeriod::class,
            self::GeoRefs => EntityGeoRef::class,
            self::Chronicles => Chronicle::class,
            self::ChronicleEntries => ChronicleEntry::class,
        };
    }

    /**
     * Line keys in emitted order, without `_op`.
     *
     * @return list<string>
     */
    public function keys(): array
    {
        return match ($this) {
            self::Entities => ['id', 'name', 'entity_type', 'wikidata_id', 'summary', 'significance', 'impact_score', 'display_priority', 'icon_class', 'confidence', 'verification_status', 'date_method', 'date_confidence', 'duration_type', 'location_method', 'location_confidence', 'primary_geo_ref_id', 'attributes', 'source_citations', 'aliases', 'tags', 'temporal_ranges', 'locations'],
            self::Relationships => ['id', 'source_entity_id', 'target_entity_id', 'relationship_type', 'temporal_start', 'temporal_end', 'start_year', 'end_year', 'description', 'confidence', 'derive_geometry_period', 'source_citations'],
            self::GeometryPeriods => ['id', 'entity_id', 'period_type', 'start_year', 'end_year', 'description', 'confidence', 'provenance_mode', 'relationship_id', 'source_event_id', 'geom', 'territory_geom'],
            self::GeoRefs => ['id', 'entity_id', 'provider', 'external_type', 'external_id', 'match_role', 'retrieval_method', 'temporal_start', 'temporal_end', 'temporal_start_year', 'temporal_end_year', 'geometry_period_id', 'match_score', 'is_active', 'external_tags', 'source_meta'],
            self::Chronicles => ['id', 'slug', 'title', 'source_type', 'source_reference', 'status', 'start_year', 'end_year', 'impact_score', 'approximate_location', 'metadata', 'tags'],
            self::ChronicleEntries => ['id', 'chronicle_id', 'sequence_order', 'start_year', 'end_year', 'impact_score', 'primary_relationship_id', 'narrative_text', 'notes', 'approximate_location', 'source_evidence', 'generated_by', 'entities'],
        };
    }

    public function schemaPath(): string
    {
        return BundleFormat::schemaDir().'/'.$this->value.'.schema.json';
    }
}
