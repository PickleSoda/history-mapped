<?php

declare(strict_types=1);

namespace App\Http\Requests\Web;

use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class StoreChronicleRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user() !== null;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'title' => ['required', 'string', 'max:500'],
            'slug' => ['sometimes', 'nullable', 'string', 'max:255', 'unique:chronicles,slug'],
            'source_type' => ['sometimes', 'nullable', 'string', Rule::enum(SourceType::class)],
            'source_reference' => ['sometimes', 'nullable', 'string', 'max:2000'],
            'status' => ['sometimes', 'nullable', 'string', Rule::enum(ChronicleStatus::class)],
            'start_year' => ['sometimes', 'nullable', 'integer'],
            'end_year' => ['sometimes', 'nullable', 'integer'],
            'impact_score' => ['sometimes', 'nullable', 'integer'],
            'approximate_location' => ['sometimes', 'nullable', 'array'],
            'metadata' => ['sometimes', 'nullable', 'array'],
            'entries' => ['sometimes', 'nullable', 'array'],
            'entries.*.sequence_order' => ['sometimes', 'integer', 'min:0'],
            'entries.*.narrative_text' => ['required', 'string', 'max:10000'],
            'entries.*.notes' => ['sometimes', 'nullable', 'string', 'max:5000'],
            'entries.*.source_evidence' => ['sometimes', 'nullable', 'array'],
            'entries.*.primary_relationship_id' => ['sometimes', 'nullable', 'string', 'uuid'],
            'entries.*.secondary_entity_ids' => ['sometimes', 'nullable', 'array'],
            'entries.*.secondary_entity_ids.*' => ['string', 'uuid'],
            'entries.*.start_year' => ['sometimes', 'nullable', 'integer'],
            'entries.*.end_year' => ['sometimes', 'nullable', 'integer'],
            'entries.*.impact_score' => ['sometimes', 'nullable', 'integer'],
            'entries.*.approximate_location' => ['sometimes', 'nullable', 'array'],
        ];
    }
}
