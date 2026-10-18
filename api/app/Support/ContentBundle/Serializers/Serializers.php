<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use App\Support\ContentBundle\RecordType;

/**
 * RecordType -> serializer lookup, resolved through the container.
 */
final class Serializers
{
    public static function for(RecordType $type): RecordSerializer
    {
        return app(match ($type) {
            RecordType::Entities => EntitySerializer::class,
            RecordType::Relationships => RelationshipSerializer::class,
            RecordType::GeometryPeriods => GeometryPeriodSerializer::class,
            RecordType::GeoRefs => GeoRefSerializer::class,
            RecordType::Chronicles => ChronicleSerializer::class,
            RecordType::ChronicleEntries => ChronicleEntrySerializer::class,
        });
    }

    /** @return array<string, RecordSerializer> keyed by RecordType value, in RecordType order */
    public static function all(): array
    {
        $all = [];
        foreach (RecordType::cases() as $type) {
            $all[$type->value] = self::for($type);
        }

        return $all;
    }
}
