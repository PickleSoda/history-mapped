<?php

declare(strict_types=1);

namespace App\Mcp\Support;

use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\JsonSchema\Types\ArrayType;
use Illuminate\JsonSchema\Types\ObjectType;
use Illuminate\JsonSchema\Types\Type;

/**
 * Output-schema fragments shared by the tools, so every tool describes an
 * EntitySummary (or a chronicle row) identically.
 */
final class OutputSchemas
{
    public static function entitySummary(JsonSchema $s): ObjectType
    {
        return $s->object(self::entityFields($s))->description('An atlas entity.');
    }

    /**
     * @return array<string, Type>
     */
    public static function entityFields(JsonSchema $s): array
    {
        return [
            'id' => $s->string()->description('Entity uuid.')->required(),
            'name' => $s->string()->required(),
            'type' => $s->string()->description('Entity type value, e.g. person, city, event_battle.')->required(),
            'type_label' => $s->string()->description('Readable type, e.g. "Battle".')->required(),
            'group' => $s->string()->description('Entity group (political/social, places, events, economic, cultural).')->required(),
            'start_year' => $s->integer()->description('Signed start year (BC negative), null if unknown.')->nullable()->required(),
            'end_year' => $s->integer()->description('Signed end year, null if unknown or ongoing.')->nullable()->required(),
            'date_label' => $s->string()->description('Human date text, e.g. "1769–1821" or "44 BC".')->nullable()->required(),
            'summary' => $s->string()->description('Short summary, at most 300 characters.')->nullable()->required(),
            'lng' => $s->number()->description('Longitude of the primary location point.')->nullable()->required(),
            'lat' => $s->number()->description('Latitude of the primary location point.')->nullable()->required(),
            'place' => $s->string()->description('Name of the primary location.')->nullable()->required(),
            'image_url' => $s->string()->description('Thumbnail URL (Wikimedia Commons), if the entity has an image.')->nullable()->required(),
            'impact_score' => $s->integer()->description('Historical impact, higher is more important.')->nullable()->required(),
            'verification_status' => $s->string()->description('pipeline_draft and needs_review records are unreviewed.')->required(),
            'atlas_url' => $s->string()->description('Open this entity in the atlas. Cite it.')->required(),
        ];
    }

    public static function entityList(JsonSchema $s): ArrayType
    {
        return $s->array()->items(self::entitySummary($s));
    }

    /** @return array<string, Type> */
    public static function chronicleBriefFields(JsonSchema $s): array
    {
        return [
            'slug' => $s->string()->required(),
            'title' => $s->string()->required(),
            'start_year' => $s->integer()->nullable()->required(),
            'end_year' => $s->integer()->nullable()->required(),
            'summary' => $s->string()->nullable()->required(),
            'atlas_url' => $s->string()->description('Open this chronicle in the atlas. Cite it.')->required(),
        ];
    }
}
