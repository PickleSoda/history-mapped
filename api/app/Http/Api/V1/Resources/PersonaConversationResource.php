<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Entity;
use App\Models\PersonaConversation;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;
use Illuminate\Support\Str;

/**
 * One row of "the people I have talked with" (no messages).
 *
 * @mixin PersonaConversation
 */
class PersonaConversationResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        $last = $this->relationLoaded('latestMessage') ? $this->latestMessage : null;

        return [
            'id' => $this->id,
            'entity' => self::speaker($this->entity),
            'last_message' => $last ? [
                'role' => $last->role,
                'snippet' => Str::limit(preg_replace('/\s+/', ' ', $last->content) ?? '', 110),
                'at' => $last->created_at?->toISOString(),
            ] : null,
            'last_message_at' => $this->last_message_at?->toISOString(),
        ];
    }

    /**
     * The speaker card shared by the list and the conversation view.
     *
     * @return array<string, mixed>
     */
    public static function speaker(Entity $entity): array
    {
        $range = $entity->relationLoaded('primaryTemporalRange') ? $entity->primaryTemporalRange : null;

        return [
            'id' => $entity->entity_id,
            'name' => $entity->name,
            'entity_type' => $entity->entity_type?->value,
            'temporal_start' => $range?->start_date,
            'temporal_end' => $range?->end_date,
            'image' => self::image($entity->attributes['media_refs'] ?? null),
        ];
    }

    /**
     * The first picture of `media_refs` with its credit (linked, never copied).
     *
     * @return array<string, string|null>|null
     */
    private static function image(mixed $refs): ?array
    {
        foreach (is_array($refs) ? $refs : [] as $ref) {
            if (! is_array($ref) || empty($ref['url']) || ! is_string($ref['url'])) {
                continue;
            }
            $kind = (string) ($ref['type'] ?? $ref['kind'] ?? 'image');
            if (! str_contains($kind, 'image') && ! preg_match('/\.(png|jpe?g|gif|webp|avif|svg)(\?.*)?$/i', $ref['url'])) {
                continue;
            }

            return [
                'url' => $ref['url'],
                'author' => isset($ref['author']) ? (string) $ref['author'] : null,
                'license' => isset($ref['license']) ? (string) $ref['license'] : null,
                'license_url' => isset($ref['license_url']) ? (string) $ref['license_url'] : null,
                'page_url' => isset($ref['page_url']) ? (string) $ref['page_url'] : null,
            ];
        }

        return null;
    }
}
