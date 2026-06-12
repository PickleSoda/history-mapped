<?php

declare(strict_types=1);

namespace App\Http\Requests\Web;

use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use App\Models\Chronicle;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class UpdateChronicleRequest extends FormRequest
{
    private ?Chronicle $chronicle = null;

    public function authorize(): bool
    {
        return $this->user() !== null;
    }

    private function getChronicle(): Chronicle
    {
        if ($this->chronicle === null) {
            $this->chronicle = Chronicle::where('slug', $this->route('slug'))->firstOrFail();
        }
        return $this->chronicle;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        $chronicle = $this->getChronicle();

        return [
            'title' => ['sometimes', 'string', 'max:500'],
            'slug' => [
                'sometimes',
                'nullable',
                'string',
                'max:255',
                Rule::unique('chronicles', 'slug')->ignore($chronicle->chronicle_id, 'chronicle_id'),
            ],
            'source_type' => ['sometimes', 'nullable', 'string', Rule::enum(SourceType::class)],
            'source_reference' => ['sometimes', 'nullable', 'string', 'max:2000'],
            'status' => ['sometimes', 'nullable', 'string', Rule::enum(ChronicleStatus::class)],
            'metadata' => ['sometimes', 'nullable', 'array'],
            'entries' => ['sometimes', 'nullable', 'array'],
            'entries.*.sequence_order' => ['sometimes', 'integer', 'min:0'],
            'entries.*.narrative_text' => ['required', 'string', 'max:10000'],
            'entries.*.notes' => ['sometimes', 'nullable', 'string', 'max:5000'],
            'entries.*.source_evidence' => ['sometimes', 'nullable', 'array'],
            'entries.*.primary_relationship_id' => ['sometimes', 'nullable', 'string', 'uuid'],
            'entries.*.secondary_entity_ids' => ['sometimes', 'nullable', 'array'],
            'entries.*.secondary_entity_ids.*' => ['string', 'uuid'],
        ];
    }
}
