<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Support\ContributionFields;
use App\Support\TextDiff;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * A user's proposed correction to one prose field of one record, stored as a
 * base snapshot + proposal + word-level diff and held for staff review.
 */
#[Fillable([
    'user_id', 'target_type', 'target_id', 'field', 'base_text', 'proposed_text',
    'diff', 'note', 'status', 'reviewer_id', 'review_note', 'reviewed_at',
])]
class Contribution extends Model
{
    /**
     * Label, links and live field values of the target, filled for responses
     * by DescribeContributionTargetsAction (not a column).
     *
     * @var array{label: string, admin_url: string, public_url: string, fields: array<string, string|null>}|null
     */
    public ?array $targetInfo = null;

    protected $attributes = [
        'status' => 'pending',
    ];

    protected function casts(): array
    {
        return [
            'target_type' => ContributionTargetType::class,
            'status' => ContributionStatus::class,
            'diff' => 'array',
            'reviewed_at' => 'datetime',
        ];
    }

    /** @return BelongsTo<User, $this> */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /** @return BelongsTo<User, $this> */
    public function reviewer(): BelongsTo
    {
        return $this->belongsTo(User::class, 'reviewer_id');
    }

    public function isPending(): bool
    {
        return $this->status === ContributionStatus::Pending;
    }

    /** The record being corrected, or null once it has been deleted. */
    public function target(): ?Model
    {
        return $this->target_type->find($this->target_id);
    }

    /** The field's live value on the target (null if the target is gone). */
    public function currentText(?Model $target = null): ?string
    {
        $target ??= $this->target();

        return $target === null ? null : ContributionFields::read($target, $this->field);
    }

    /** True when the field changed after this contribution was submitted. */
    public function isStaleAgainst(?string $current): bool
    {
        return $current === null || ! ContributionFields::same($this->field, $current, $this->base_text);
    }

    /** @return array{added: int, removed: int} */
    public function stats(): array
    {
        return TextDiff::stats($this->diff ?? []);
    }
}
