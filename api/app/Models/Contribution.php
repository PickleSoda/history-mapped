<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ContributionKind;
use App\Enums\ContributionSource;
use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Support\ContributionFields;
use App\Support\TextDiff;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * A user's proposal held for staff review. Either (`edit`) a correction to one
 * prose field of one record, stored as a base snapshot + proposal + word-level
 * diff, or (`create`) a new entity or relationship, stored as a validated
 * `payload` and only created when a moderator approves it.
 */
#[Fillable([
    'user_id', 'kind', 'payload', 'source', 'client', 'target_type', 'target_id', 'field', 'base_text', 'proposed_text',
    'diff', 'note', 'status', 'reviewer_id', 'review_note', 'reviewed_at',
])]
class Contribution extends Model
{
    /**
     * Label, links and live field values of the target, filled for responses
     * by DescribeContributionTargetsAction (not a column).
     *
     * @var array{label: string, admin_url: string|null, public_url: string|null, fields: array<string, string|null>}|null
     */
    public ?array $targetInfo = null;

    protected $attributes = [
        'status' => 'pending',
        'kind' => 'edit',
        'source' => 'atlas',
    ];

    protected function casts(): array
    {
        return [
            'kind' => ContributionKind::class,
            'source' => ContributionSource::class,
            'payload' => 'array',
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

    public function isCreate(): bool
    {
        return $this->kind === ContributionKind::Create;
    }

    public function isPending(): bool
    {
        return $this->status === ContributionStatus::Pending;
    }

    /** The record being corrected, or null once it has been deleted. */
    public function target(): ?Model
    {
        return $this->target_id === null ? null : $this->target_type->find($this->target_id);
    }

    /** The field's live value on the target (null if the target is gone). */
    public function currentText(?Model $target = null): ?string
    {
        $target ??= $this->target();

        return $target === null || $this->field === null ? null : ContributionFields::read($target, $this->field);
    }

    /** True when the field changed after this contribution was submitted. */
    public function isStaleAgainst(?string $current): bool
    {
        if ($this->isCreate()) {
            return false; // a proposal for a new record has no base text to go stale
        }

        return $current === null
            || ! ContributionFields::same((string) $this->field, $current, (string) $this->base_text);
    }

    /** @return array{added: int, removed: int} */
    public function stats(): array
    {
        return TextDiff::stats($this->diff ?? []);
    }
}
