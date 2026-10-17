<?php

declare(strict_types=1);

namespace App\Actions\Saved;

use App\Enums\SaveableType;
use App\Models\Star;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

/**
 * Star an item for a user (idempotent) and optionally file it in some of the
 * user's folders. Folder ids that are not the user's are rejected.
 */
class StarItemAction
{
    /**
     * @param  list<int>  $folderIds
     */
    public function __invoke(User $user, SaveableType $type, string $id, array $folderIds = []): Star
    {
        if (! $type->exists($id)) {
            throw ValidationException::withMessages(['id' => "No {$type->value} with this id."]);
        }

        $ownedFolderIds = $folderIds === []
            ? []
            : $user->savedFolders()->whereKey($folderIds)->pluck('id')->all();
        if (count($ownedFolderIds) !== count(array_unique($folderIds))) {
            throw ValidationException::withMessages(['folder_ids' => 'Unknown folder.']);
        }

        return DB::transaction(function () use ($user, $type, $id, $ownedFolderIds): Star {
            $star = Star::query()->firstOrCreate([
                'user_id' => $user->id,
                'starrable_type' => $type->value,
                'starrable_id' => $id,
            ]);

            if ($ownedFolderIds !== []) {
                $star->folders()->syncWithoutDetaching($ownedFolderIds);
                $star->touch();
            }

            return $star;
        });
    }
}
