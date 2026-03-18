<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Http\Api\V1\Resources\ReferenceResource;
use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;

/**
 * Serves reference/lookup table data.
 *
 * All reference data is cached for 24 hours since it rarely changes.
 * The 10 reference tables provide enum-like lookup values for the frontend.
 */
class ReferenceController extends Controller
{
    /**
     * Allowed reference table names mapped to their DB table names.
     * Prevents arbitrary table access.
     *
     * @var array<string, string>
     */
    private const ALLOWED_TABLES = [
        'geographic-regions' => 'ref_geographic_regions',
        'historical-periods' => 'ref_historical_periods',
        'historiographical-schools' => 'ref_historiographical_schools',
        'calendar-systems' => 'ref_calendar_systems',
        'era-date-lookup' => 'ref_era_date_lookup',
        'writing-systems' => 'ref_writing_systems',
        'religious-traditions' => 'ref_religious_traditions',
        'measurement-units' => 'ref_measurement_units',
        'language-families' => 'ref_language_families',
        'source-type-definitions' => 'ref_source_type_definitions',
    ];

    /**
     * GET /api/v1/reference
     *
     * List available reference tables.
     */
    public function index(): JsonResponse
    {
        return response()->json([
            'data' => array_keys(self::ALLOWED_TABLES),
        ]);
    }

    /**
     * GET /api/v1/reference/{table}
     *
     * Return all rows from a reference table (cached 24h).
     */
    public function show(string $table): AnonymousResourceCollection|JsonResponse
    {
        if (! isset(self::ALLOWED_TABLES[$table])) {
            return response()->json([
                'message' => 'Unknown reference table.',
                'available' => array_keys(self::ALLOWED_TABLES),
            ], 404);
        }

        $dbTable = self::ALLOWED_TABLES[$table];
        $cacheKey = "reference.{$table}";

        $rows = Cache::remember($cacheKey, now()->addHours(24), function () use ($dbTable) {
            return DB::table($dbTable)
                ->orderBy('sort_order')
                ->get()
                ->map(fn ($row) => (array) $row)
                ->all();
        });

        return ReferenceResource::collection($rows);
    }

    /**
     * POST /api/v1/reference/cache/clear
     *
     * Clear all reference table caches (admin operation).
     */
    public function clearCache(): JsonResponse
    {
        foreach (array_keys(self::ALLOWED_TABLES) as $table) {
            Cache::forget("reference.{$table}");
        }

        return response()->json(['message' => 'Reference cache cleared.']);
    }
}
