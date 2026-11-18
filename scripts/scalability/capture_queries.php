<?php

// Captures the SQL (with bindings) the API runs for each benchmarked request,
// on a cache miss. Run inside the app container:
//   php artisan tinker --execute='require "/tmp/capture_queries.php";' > queries.json
// See docs/architecture/scalability.md.

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

config(['cache.default' => 'array']);

$rome = DB::table('entities')->where('wikidata_id', 'Q2277')->value('entity_id');
$europe = ['bbox_min_lng' => -15, 'bbox_min_lat' => 30, 'bbox_max_lng' => 45, 'bbox_max_lat' => 62];
$world = ['bbox_min_lng' => -180, 'bbox_min_lat' => -70, 'bbox_max_lng' => 180, 'bbox_max_lat' => 80];

$requests = [
    'list_europe_1600' => ['/api/v1/entities', ['sort' => 'impact', 'per_page' => 50, 'page' => 1, 'exists_at' => 1600] + $europe],
    'list_world_-50' => ['/api/v1/entities', ['sort' => 'impact', 'per_page' => 50, 'page' => 1, 'exists_at' => -50] + $world],
    'search_ro' => ['/api/v1/entities', ['sort' => 'relevance', 'per_page' => 30, 'search' => 'ro']],
    'search_rome' => ['/api/v1/entities', ['sort' => 'relevance', 'per_page' => 30, 'search' => 'rome']],
    'search_charles' => ['/api/v1/entities', ['sort' => 'relevance', 'per_page' => 30, 'search' => 'charles']],
    'tags' => ['/api/v1/tags', []],
    'entity_detail' => ["/api/v1/entities/{$rome}", []],
];

$out = [];
foreach ($requests as $name => [$uri, $params]) {
    DB::flushQueryLog();
    DB::enableQueryLog();
    $response = app()->handle(Request::create($uri, 'GET', $params));
    DB::disableQueryLog();
    $out[$name] = [
        'status' => $response->getStatusCode(),
        'queries' => array_map(fn (array $q) => ['sql' => $q['query'], 'bindings' => $q['bindings']], DB::getQueryLog()),
    ];
}

echo json_encode($out, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), "\n";
