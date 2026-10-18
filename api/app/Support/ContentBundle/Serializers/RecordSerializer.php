<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;

/**
 * Turns one model into one bundle line (an ordered array), one implementation per record type.
 */
interface RecordSerializer
{
    public function type(): RecordType;

    /** Base query for this type: eager loads and geojson selects; callers add scope + ordering. */
    public function query(): Builder;

    /** @return array<string, mixed> keys exactly RecordType::keys(), in order */
    public function serialize(Model $model, Profile $profile): array;
}
