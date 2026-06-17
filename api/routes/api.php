<?php

use App\Http\Api\V1\Controllers\EntityChronicleController;
use App\Http\Api\V1\Controllers\EntityController;
use App\Http\Api\V1\Controllers\EntityGeoRefController;
use App\Http\Api\V1\Controllers\EntityRelationshipController;
use App\Http\Api\V1\Controllers\EntityTimelineController;
use App\Http\Api\V1\Controllers\MapResolutionController;
use App\Http\Api\V1\Controllers\ReferenceController;
use App\Http\Api\V1\Controllers\SourceController;
use App\Http\Controllers\Api\V1\ChronicleController;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

Route::prefix('v1')->group(function () {

    // ── Health Check ─────────────────────────────────────────
    Route::get('/health', fn () => response()->json([
        'status' => 'ok',
        'timestamp' => now()->toISOString(),
    ]))->name('api.v1.health');

    // ── Public Read Endpoints ────────────────────────────────
    // No auth required — the SPA and third-party consumers need these.

    // Entities
    Route::get('/entities/map/year', [EntityController::class, 'mapByYear'])
        ->name('api.v1.entities.map.year');

    Route::get('/entities/map', [EntityController::class, 'map'])
        ->name('api.v1.entities.map');

    // Read-only OHM-feature resolution for the public atlas (click an OHM
    // basemap feature -> matching entity). The editor's mutating counterpart is
    // the permission-gated POST below.
    Route::get('/map/resolve-ohm-feature', [MapResolutionController::class, 'resolveOhmFeature'])
        ->name('api.v1.map.resolve-ohm-feature.show');

    Route::get('/entities', [EntityController::class, 'index'])
        ->name('api.v1.entities.index');

    Route::get('/entities/{entity}', [EntityController::class, 'show'])
        ->name('api.v1.entities.show');

    Route::get('/entities/{entity}/geography-references', [EntityGeoRefController::class, 'index'])
        ->name('api.v1.entities.geography-references.index');

    Route::get('/entities/{entity}/geography-references/search', [EntityGeoRefController::class, 'search'])
        ->name('api.v1.entities.geography-references.search');

    // Entity Relationships
    Route::get('/entities/{entity}/relationships', [EntityRelationshipController::class, 'index'])
        ->name('api.v1.entities.relationships.index');

    Route::get('/entities/{entity}/chronicles', [EntityChronicleController::class, 'index'])
        ->name('api.v1.entities.chronicles.index');

    Route::get('/entities/{entity}/timeline', [EntityTimelineController::class, 'index'])
        ->name('api.v1.entities.timeline.index');

    Route::get('/entities/{entity}/timeline/{timelineEntry}', [EntityTimelineController::class, 'show'])
        ->name('api.v1.entities.timeline.show');

    // Sources
    Route::get('/sources', [SourceController::class, 'index'])
        ->name('api.v1.sources.index');

    Route::get('/sources/{source}', [SourceController::class, 'show'])
        ->name('api.v1.sources.show');

    // Chronicles
    Route::get('/chronicles', [ChronicleController::class, 'index'])
        ->name('api.v1.chronicles.index');

    Route::get('/chronicles/{slug}', [ChronicleController::class, 'show'])
        ->name('api.v1.chronicles.show');

    // Reference Tables (cached)
    Route::get('/reference', [ReferenceController::class, 'index'])
        ->name('api.v1.reference.index');

    Route::get('/reference/{table}', [ReferenceController::class, 'show'])
        ->name('api.v1.reference.show');

    // ── Authenticated Write Endpoints ────────────────────────
    // Reads above are public; every write is permission-gated. The `admin` role
    // bypasses all permission checks via a Gate::before super-user rule.
    Route::middleware('auth:sanctum')->group(function () {

        Route::get('/user', fn (Request $request) => $request->user())
            ->name('api.v1.user');

        // Entities CRUD
        Route::middleware('permission:entities.write')->group(function () {
            Route::post('/entities', [EntityController::class, 'store'])
                ->name('api.v1.entities.store');

            Route::put('/entities/{entity}', [EntityController::class, 'update'])
                ->name('api.v1.entities.update');

            Route::delete('/entities/{entity}', [EntityController::class, 'destroy'])
                ->name('api.v1.entities.destroy');
        });

        // Geometry / geo-references + OHM feature resolution (editorial geodata tool)
        Route::middleware('permission:geometry.write')->group(function () {
            Route::post('/entities/{entity}/geography-references', [EntityGeoRefController::class, 'store'])
                ->name('api.v1.entities.geography-references.store');

            Route::delete('/entities/{entity}/geography-references/{ref}', [EntityGeoRefController::class, 'destroy'])
                ->name('api.v1.entities.geography-references.destroy');

            Route::post('/map/resolve-ohm-feature', [MapResolutionController::class, 'resolveOhmFeature'])
                ->name('api.v1.map.resolve-ohm-feature');
        });

        // Entity Relationships (write)
        Route::middleware('permission:relationships.write')->group(function () {
            Route::post('/entities/{entity}/relationships', [EntityRelationshipController::class, 'store'])
                ->name('api.v1.entities.relationships.store');

            Route::delete('/entities/{entity}/relationships/{relationship}', [EntityRelationshipController::class, 'destroy'])
                ->name('api.v1.entities.relationships.destroy');
        });

        // Sources (write)
        Route::middleware('permission:sources.write')->group(function () {
            Route::post('/sources', [SourceController::class, 'store'])
                ->name('api.v1.sources.store');
        });

        // Reference cache management
        Route::middleware('permission:reference.manage')->group(function () {
            Route::post('/reference/cache/clear', [ReferenceController::class, 'clearCache'])
                ->name('api.v1.reference.cache.clear');
        });
    });
});
