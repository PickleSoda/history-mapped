<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Star;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * A starred item. `item` is the target's summary card — resolved in bulk by
 * ResolveSavedItemsAction — or null once the target has been deleted.
 *
 * @mixin Star
 */
class StarResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'type' => $this->starrable_type->value,
            'target_id' => $this->starrable_id,
            'folder_ids' => $this->folders->pluck('id')->values()->all(),
            'created_at' => $this->created_at?->toISOString(),
            'item' => $this->resolvedItem,
        ];
    }
}
