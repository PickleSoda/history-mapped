<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Discover\GetDailyQuestAction;
use App\Actions\Discover\GetForYouAction;
use App\Actions\Discover\GetMeanwhileAction;
use App\Actions\Discover\GetOnThisDayAction;
use App\Http\Api\V1\Requests\DiscoverForYouRequest;
use App\Http\Api\V1\Requests\DiscoverMeanwhileRequest;
use App\Http\Api\V1\Requests\DiscoverOnThisDayRequest;
use App\Http\Api\V1\Requests\DiscoverQuestRequest;
use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;

/**
 * "Today" on the browse page and in the atlas: four small feeds built from
 * what the atlas already holds (docs/schemas/rest-api.md, "Discover").
 */
class DiscoverController extends Controller
{
    /**
     * GET /api/v1/discover/on-this-day?date=YYYY-MM-DD
     *
     * Up to eight things that happened on the date's month and day: events,
     * foundings, births and deaths, each with the year it happened.
     */
    public function onThisDay(DiscoverOnThisDayRequest $request, GetOnThisDayAction $action): JsonResponse
    {
        return $this->shared($action(...$request->monthAndDay()));
    }

    /**
     * GET /api/v1/discover/meanwhile?year=1066
     *
     * For each world region, the most notable event around the year and the
     * most notable state standing in it, west to east.
     */
    public function meanwhile(DiscoverMeanwhileRequest $request, GetMeanwhileAction $action): JsonResponse
    {
        return $this->shared($action((int) $request->validated('year')));
    }

    /**
     * GET /api/v1/discover/quest?date=YYYY-MM-DD
     *
     * The day's expedition: three battles to find on the map and the
     * timeline (easy, medium, hard), the same for everyone that day.
     */
    public function quest(DiscoverQuestRequest $request, GetDailyQuestAction $action): JsonResponse
    {
        return $this->shared($action($request->day()));
    }

    /**
     * GET /api/v1/discover/for-you?ids=uuid,uuid,…
     *
     * Entities, chronicles and battle maps related to the entities a browser
     * opened lately (most recent first).
     */
    public function forYou(DiscoverForYouRequest $request, GetForYouAction $action): JsonResponse
    {
        return response()->json(['data' => $action($request->ids())])
            ->header('Cache-Control', 'private, max-age='.(int) config('discover.cache.for_you_max_age'));
    }

    /**
     * An answer that is the same for every reader.
     *
     * @param  array<string, mixed>  $data
     */
    private function shared(array $data): JsonResponse
    {
        return response()->json(['data' => $data])
            ->header('Cache-Control', 'public, max-age='.(int) config('discover.cache.max_age'));
    }
}
