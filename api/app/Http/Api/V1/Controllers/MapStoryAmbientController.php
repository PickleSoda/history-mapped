<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\MapStory\AmbientMapStoriesAction;
use App\Http\Api\V1\Requests\AmbientMapStoriesRequest;
use App\Http\Controllers\Controller;
use Illuminate\Http\Response;

class MapStoryAmbientController extends Controller
{
    /**
     * GET /api/v1/map-stories/ambient?year=Y&bbox=w,s,e,n
     *
     * The opt-in (`ambient`) stories to draw faintly on the plain atlas at
     * year Y, each as its state at that year. ETag-cached like /entities/map.
     */
    public function __invoke(AmbientMapStoriesRequest $request, AmbientMapStoriesAction $action): Response
    {
        $year = (int) $request->validated('year');
        $bbox = $request->bbox();

        $response = new Response('', 200, ['Content-Type' => 'application/json', 'Cache-Control' => 'public, max-age=60']);
        $response->setEtag($action->etag($year, $bbox));
        if ($response->isNotModified($request)) {
            return $response;
        }

        return $response->setContent($action($year, $bbox));
    }
}
