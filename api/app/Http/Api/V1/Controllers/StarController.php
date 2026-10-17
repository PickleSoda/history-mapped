<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Saved\ResolveSavedItemsAction;
use App\Actions\Saved\StarItemAction;
use App\Enums\SaveableType;
use App\Http\Api\V1\Requests\StoreStarRequest;
use App\Http\Api\V1\Resources\StarResource;
use App\Http\Controllers\Controller;
use App\Models\Star;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Http\Response;
use Illuminate\Validation\Rule;

class StarController extends Controller
{
    /**
     * GET /api/v1/me/stars/keys
     *
     * Every star of the user as a compact key list, so the SPA can render
     * star state anywhere without a request per item.
     */
    public function keys(Request $request): JsonResponse
    {
        $stars = $request->user()->stars()
            ->with('folders:saved_folders.id')
            ->get(['id', 'starrable_type', 'starrable_id']);

        return response()->json([
            'data' => $stars->map(fn (Star $s) => [
                'type' => $s->starrable_type->value,
                'id' => $s->starrable_id,
                'star_id' => $s->id,
                'folder_ids' => $s->folders->pluck('id')->values()->all(),
            ])->values(),
        ]);
    }

    /**
     * GET /api/v1/me/stars
     *
     * Starred items, newest first, optionally narrowed to one type and/or one
     * of the user's folders.
     */
    public function index(Request $request, ResolveSavedItemsAction $resolve): AnonymousResourceCollection
    {
        $user = $request->user();
        $filters = $request->validate([
            'type' => ['sometimes', 'nullable', Rule::enum(SaveableType::class)],
            'folder' => ['sometimes', 'nullable', 'integer'],
            'per_page' => ['sometimes', 'integer', 'min:1', 'max:100'],
        ]);

        $query = $user->stars()->with('folders:saved_folders.id')->latest()->orderByDesc('id');
        if (! empty($filters['type'])) {
            $query->where('starrable_type', $filters['type']);
        }
        if (! empty($filters['folder'])) {
            $folder = $user->savedFolders()->findOrFail($filters['folder']);
            $query->whereHas('folders', fn ($q) => $q->whereKey($folder->id));
        }

        $stars = $query->paginate((int) ($filters['per_page'] ?? 30));
        self::attachItems($stars->getCollection(), $resolve);

        return StarResource::collection($stars);
    }

    /**
     * POST /api/v1/me/stars
     *
     * Idempotent: 201 for a new star, 200 when it already existed.
     */
    public function store(StoreStarRequest $request, StarItemAction $star, ResolveSavedItemsAction $resolve): JsonResponse
    {
        $data = $request->validated();
        $model = $star(
            $request->user(),
            SaveableType::from($data['type']),
            $data['id'],
            array_map('intval', $data['folder_ids'] ?? []),
        );
        $model->load('folders:saved_folders.id');
        self::attachItems(collect([$model]), $resolve);

        return (new StarResource($model))
            ->response()
            ->setStatusCode($model->wasRecentlyCreated ? 201 : 200);
    }

    /**
     * DELETE /api/v1/me/stars/{type}/{id}
     *
     * Unstar; the item leaves every folder it was in.
     */
    public function destroy(Request $request, string $type, string $id): Response
    {
        $request->user()->stars()
            ->forTarget(SaveableType::from($type), $id)
            ->delete();

        return response()->noContent();
    }

    /**
     * @param  iterable<Star>  $stars
     */
    public static function attachItems(iterable $stars, ResolveSavedItemsAction $resolve): void
    {
        $items = $resolve($stars);
        foreach ($stars as $star) {
            $star->resolvedItem = $items["{$star->starrable_type->value}:{$star->starrable_id}"] ?? null;
        }
    }
}
