<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * Generic resource for reference/lookup tables.
 *
 * Returns all columns except created_at/updated_at timestamps,
 * suitable for the 10 reference tables (ref_geographic_regions, etc.).
 *
 * @mixin Model
 */
class ReferenceResource extends JsonResource
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(Request $request): array
    {
        // Resource may wrap a plain array (from cache) or a Model/stdClass.
        $data = is_array($this->resource)
            ? $this->resource
            : parent::toArray($request);

        // Remove timestamps — reference data doesn't need them in API responses
        unset($data['created_at'], $data['updated_at']);

        return $data;
    }
}
