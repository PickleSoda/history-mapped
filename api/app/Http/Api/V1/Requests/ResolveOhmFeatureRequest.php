<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefProvider;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class ResolveOhmFeatureRequest extends FormRequest
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
            'provider' => ['required', 'string', Rule::enum(GeoRefProvider::class)],
            'external_type' => ['required', 'string', Rule::enum(GeoRefExternalType::class)],
            'external_id' => ['required', 'string', 'max:255'],
            'target_year' => ['required', 'integer'],
        ];
    }
}
