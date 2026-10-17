<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * The signed-in account for the public SPA. `can` is evaluated through the
 * Gate, so the `admin` super-user role reads true everywhere.
 *
 * @mixin User
 */
class MeResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'name' => $this->name,
            'email' => $this->email,
            'roles' => $this->getRoleNames()->values()->all(),
            'can' => [
                'access_admin' => $this->can('admin.access'),
                'contribute' => $this->can('contributions.create'),
                'review_contributions' => $this->can('contributions.review'),
            ],
            'admin_url' => url('/dashboard'),
        ];
    }
}
