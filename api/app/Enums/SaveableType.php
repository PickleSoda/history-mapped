<?php

declare(strict_types=1);

namespace App\Enums;

use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\EntityRelationship;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Str;

/**
 * What a user can star / put in a saved folder. The value is what the API and
 * the `stars.starrable_type` column carry; ids are the model's primary key.
 */
enum SaveableType: string
{
    case Entity = 'entity';
    case Chronicle = 'chronicle';
    case Relationship = 'relationship';

    /** @return class-string<Model> */
    public function modelClass(): string
    {
        return match ($this) {
            self::Entity => Entity::class,
            self::Chronicle => Chronicle::class,
            self::Relationship => EntityRelationship::class,
        };
    }

    /** Primary keys are Postgres `uuid`s; anything else cannot match. */
    public function exists(string $id): bool
    {
        $class = $this->modelClass();

        return Str::isUuid($id) && $class::query()->whereKey($id)->exists();
    }
}
