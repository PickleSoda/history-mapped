<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Actions\Entity\MapFocusAction;
use App\Enums\EntityGroup;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * GET /api/v1/entities/map/focus?related_to={id}&depth=2
 * GET /api/v1/entities/map/focus?search=napoleon
 *
 * One of `related_to` or `search`, never both.
 */
class MapFocusRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'related_to' => ['required_without:search', 'prohibits:search', 'uuid'],
            'depth' => ['sometimes', 'integer', 'in:1,2'],
            'search' => ['required_without:related_to', 'string', 'min:2', 'max:255'],
            'groups' => ['sometimes', 'array', 'max:5'],
            'groups.*' => ['string', Rule::enum(EntityGroup::class)],
            'limit' => ['sometimes', 'integer', 'min:1', 'max:'.MapFocusAction::MAX_LIMIT],
        ];
    }
}
