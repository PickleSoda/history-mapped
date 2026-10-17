<?php

declare(strict_types=1);

namespace App\Http\Requests\Admin;

use App\Concerns\ProfileValidationRules;
use App\Models\User;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;
use Spatie\Permission\Models\Permission;
use Spatie\Permission\Models\Role;

/**
 * Validates account edits from the admin user management page. Who may change
 * which roles is decided by UpdateUserAction.
 *
 * PUT /users/{user}
 */
class UpdateUserRequest extends FormRequest
{
    use ProfileValidationRules;

    public function authorize(): bool
    {
        return true; // gated by the `users.manage` route middleware
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        $user = $this->route('user');

        return [
            ...$this->profileRules($user instanceof User ? $user->id : null),
            'roles' => ['present', 'array'],
            'roles.*' => ['string', 'distinct', Rule::exists(Role::class, 'name')],
            'permissions' => ['present', 'array'],
            'permissions.*' => ['string', 'distinct', Rule::exists(Permission::class, 'name')],
        ];
    }
}
