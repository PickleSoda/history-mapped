<?php

use App\Http\Api\V1\Controllers\EntityController;
use App\Http\Api\V1\Controllers\EntityRelationshipController;
use App\Http\Api\V1\Controllers\ReferenceController;
use App\Http\Api\V1\Controllers\SourceController;
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
    Route::get('/entities/map', [EntityController::class, 'map'])
        ->name('api.v1.entities.map');

    Route::get('/entities', [EntityController::class, 'index'])
        ->name('api.v1.entities.index');

    Route::get('/entities/{entity}', [EntityController::class, 'show'])
        ->name('api.v1.entities.show');

    // Entity Relationships
    Route::get('/entities/{entity}/relationships', [EntityRelationshipController::class, 'index'])
        ->name('api.v1.entities.relationships.index');

    // Sources
    Route::get('/sources', [SourceController::class, 'index'])
        ->name('api.v1.sources.index');

    Route::get('/sources/{source}', [SourceController::class, 'show'])
        ->name('api.v1.sources.show');

    // Reference Tables (cached)
    Route::get('/reference', [ReferenceController::class, 'index'])
        ->name('api.v1.reference.index');

    Route::get('/reference/{table}', [ReferenceController::class, 'show'])
        ->name('api.v1.reference.show');

    // ── Authenticated Write Endpoints ────────────────────────
    Route::middleware('auth:sanctum')->group(function () {

        Route::get('/user', fn (Request $request) => $request->user())
            ->name('api.v1.user');

        // Entities CRUD
        Route::post('/entities', [EntityController::class, 'store'])
            ->name('api.v1.entities.store');

        Route::put('/entities/{entity}', [EntityController::class, 'update'])
            ->name('api.v1.entities.update');

        Route::delete('/entities/{entity}', [EntityController::class, 'destroy'])
            ->name('api.v1.entities.destroy');

        // Entity Relationships (write)
        Route::post('/entities/{entity}/relationships', [EntityRelationshipController::class, 'store'])
            ->name('api.v1.entities.relationships.store');

        Route::delete('/entities/{entity}/relationships/{relationship}', [EntityRelationshipController::class, 'destroy'])
            ->name('api.v1.entities.relationships.destroy');

        // Sources (write)
        Route::post('/sources', [SourceController::class, 'store'])
            ->name('api.v1.sources.store');

        // Reference cache management (admin)
        Route::post('/reference/cache/clear', [ReferenceController::class, 'clearCache'])
            ->name('api.v1.reference.cache.clear');
    });
});
