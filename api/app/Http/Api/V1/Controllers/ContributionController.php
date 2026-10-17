<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Contribution\CloseContributionAction;
use App\Actions\Contribution\DescribeContributionTargetsAction;
use App\Actions\Contribution\SubmitContributionAction;
use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Http\Api\V1\Requests\StoreContributionRequest;
use App\Http\Api\V1\Resources\ContributionResource;
use App\Http\Controllers\Controller;
use App\Models\Contribution;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Validation\Rule;

/**
 * Text corrections from the public atlas: submit one, list your own, withdraw
 * a pending one. Review happens in the admin panel.
 */
class ContributionController extends Controller
{
    /**
     * POST /api/v1/contributions
     */
    public function store(
        StoreContributionRequest $request,
        SubmitContributionAction $submit,
        DescribeContributionTargetsAction $describe,
    ): JsonResponse {
        $data = $request->validated();
        $contribution = $submit(
            $request->user(),
            ContributionTargetType::from($data['target_type']),
            $data['target_id'],
            $data['field'],
            (string) ($data['proposed_text'] ?? ''),
            $data['note'] ?? null,
        );
        self::attachTargets([$contribution], $describe);

        return (new ContributionResource($contribution))->response()->setStatusCode(201);
    }

    /**
     * GET /api/v1/me/contributions
     */
    public function mine(Request $request, DescribeContributionTargetsAction $describe): AnonymousResourceCollection
    {
        $filters = $request->validate([
            'status' => ['sometimes', 'nullable', Rule::enum(ContributionStatus::class)],
            'per_page' => ['sometimes', 'integer', 'min:1', 'max:100'],
        ]);

        $query = $request->user()->contributions()->latest()->orderByDesc('id');
        if (! empty($filters['status'])) {
            $query->where('status', $filters['status']);
        }

        $page = $query->paginate((int) ($filters['per_page'] ?? 20));
        self::attachTargets($page->getCollection(), $describe);

        return ContributionResource::collection($page);
    }

    /**
     * POST /api/v1/me/contributions/{contribution}/withdraw
     */
    public function withdraw(
        Request $request,
        CloseContributionAction $close,
        DescribeContributionTargetsAction $describe,
        string $contribution,
    ): ContributionResource {
        $model = $request->user()->contributions()->findOrFail((int) $contribution);
        $model = $close->withdraw($model);
        self::attachTargets([$model], $describe);

        return new ContributionResource($model);
    }

    /**
     * @param  iterable<Contribution>  $contributions
     */
    public static function attachTargets(iterable $contributions, DescribeContributionTargetsAction $describe): void
    {
        $info = $describe($contributions);
        foreach ($contributions as $c) {
            $c->targetInfo = $info[DescribeContributionTargetsAction::key($c)] ?? null;
        }
    }
}
