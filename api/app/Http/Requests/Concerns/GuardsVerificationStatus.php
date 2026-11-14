<?php

declare(strict_types=1);

namespace App\Http\Requests\Concerns;

use App\Enums\VerificationStatus;
use App\Models\Entity;
use BackedEnum;
use Illuminate\Foundation\Http\FormRequest;

/**
 * Setting an entity's verification status is a sensitive action: it needs the
 * `entities.verify` permission on top of the `entities.write` permission the
 * route already enforces. Edits that leave the status alone are unaffected.
 *
 * Used by the admin form and the /api/v1 entity requests, so both paths apply
 * the same rule.
 *
 * @mixin FormRequest
 */
trait GuardsVerificationStatus
{
    /** Whether the signed-in user may make this request's status change, if any. */
    protected function mayChangeVerificationStatus(): bool
    {
        if (! $this->isChangingVerificationStatus()) {
            return true;
        }

        return $this->user()?->can('entities.verify') ?? false;
    }

    /**
     * Whether this request changes the verification status. On update that
     * means a value other than the bound entity's stored one; on create, a
     * value other than the default a new entity gets.
     */
    protected function isChangingVerificationStatus(): bool
    {
        if (! $this->has('verification_status')) {
            return false;
        }

        $requested = $this->input('verification_status');
        $entity = $this->route('entity');

        if ($entity === null) {
            return $requested !== null
                && $requested !== ''
                && $requested !== VerificationStatus::PipelineDraft->value;
        }

        // The admin routes bind the model; /api/v1 passes the uuid.
        if (is_string($entity)) {
            $entity = Entity::query()->where('entity_id', $entity)->first();
            if ($entity === null) {
                return false; // the controller answers 404
            }
        }

        $current = $entity->verification_status ?? null;
        $current = $current instanceof BackedEnum ? $current->value : $current;

        return $requested !== $current;
    }
}
