<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\Contribution;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * A contribution as its author sees it. `target_label` comes from
 * DescribeContributionTargetsAction (bulk); a deleted target reads "Removed record".
 *
 * @mixin Contribution
 */
class ContributionResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'target_type' => $this->target_type->value,
            'target_id' => $this->target_id,
            'field' => $this->field,
            'target_label' => $this->targetInfo['label'] ?? 'Removed record',
            'public_url' => $this->targetInfo['public_url'] ?? null,
            'status' => $this->status->value,
            'note' => $this->note,
            'review_note' => $this->review_note,
            'base_text' => $this->base_text,
            'proposed_text' => $this->proposed_text,
            'diff' => $this->diff,
            'stats' => $this->stats(),
            'created_at' => $this->created_at?->toISOString(),
            'reviewed_at' => $this->reviewed_at?->toISOString(),
        ];
    }
}
