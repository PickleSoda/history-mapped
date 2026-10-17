<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Saved\ResolveSavedItemsAction;
use App\Actions\Saved\StarItemAction;
use App\Enums\SaveableType;
use App\Http\Api\V1\Requests\SavedFolderRequest;
use App\Http\Api\V1\Resources\SavedFolderResource;
use App\Http\Api\V1\Resources\StarResource;
use App\Http\Controllers\Controller;
use App\Models\SavedFolder;
use App\Models\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Http\Response;
use Illuminate\Validation\ValidationException;

/**
 * The signed-in user's saved folders. Every `{folder}` is looked up through
 * the user's own folders, so another account's folder is a 404.
 */
class SavedFolderController extends Controller
{
    /**
     * GET /api/v1/me/folders
     */
    public function index(Request $request): AnonymousResourceCollection
    {
        return SavedFolderResource::collection(
            $request->user()->savedFolders()->withCount('stars')->orderBy('name')->get(),
        );
    }

    /**
     * POST /api/v1/me/folders
     */
    public function store(SavedFolderRequest $request): JsonResponse
    {
        $user = $request->user();
        if ($user->savedFolders()->count() >= SavedFolder::MAX_PER_USER) {
            throw ValidationException::withMessages([
                'name' => 'You can have at most '.SavedFolder::MAX_PER_USER.' folders.',
            ]);
        }

        $folder = $user->savedFolders()->create($request->validated());
        $folder->stars_count = 0;

        return (new SavedFolderResource($folder))->response()->setStatusCode(201);
    }

    /**
     * PATCH /api/v1/me/folders/{folder}
     */
    public function update(SavedFolderRequest $request, string $folder): SavedFolderResource
    {
        $model = $this->owned($request->user(), $folder);
        $model->update($request->validated());

        return new SavedFolderResource($model->loadCount('stars'));
    }

    /**
     * DELETE /api/v1/me/folders/{folder}
     *
     * The folder goes; its stars stay.
     */
    public function destroy(Request $request, string $folder): Response
    {
        $this->owned($request->user(), $folder)->delete();

        return response()->noContent();
    }

    /**
     * PUT /api/v1/me/folders/{folder}/items/{type}/{id}
     *
     * File an item in the folder, starring it first if needed.
     */
    public function addItem(
        Request $request,
        StarItemAction $star,
        ResolveSavedItemsAction $resolve,
        string $folder,
        string $type,
        string $id,
    ): JsonResponse {
        $model = $this->owned($request->user(), $folder);
        $starred = $star($request->user(), SaveableType::from($type), $id, [$model->id]);
        $starred->load('folders:saved_folders.id');
        StarController::attachItems(collect([$starred]), $resolve);

        // PUT is idempotent: always 200, even when it created the star.
        return (new StarResource($starred))->response()->setStatusCode(200);
    }

    /**
     * DELETE /api/v1/me/folders/{folder}/items/{type}/{id}
     *
     * Take an item out of the folder; it stays starred.
     */
    public function removeItem(Request $request, string $folder, string $type, string $id): Response
    {
        $model = $this->owned($request->user(), $folder);
        $star = $request->user()->stars()->forTarget(SaveableType::from($type), $id)->first();
        if ($star !== null) {
            $model->stars()->detach($star->id);
        }

        return response()->noContent();
    }

    private function owned(User $user, string $folder): SavedFolder
    {
        return $user->savedFolders()->findOrFail((int) $folder);
    }
}
