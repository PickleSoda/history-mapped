<?php

use App\Http\Controllers\Admin\Ai\AiChatController;
use App\Http\Controllers\Admin\Ai\AiProposalController;
use App\Http\Controllers\Admin\EntityController;
use App\Http\Controllers\Admin\EntityGeometryPeriodController;
use App\Http\Controllers\Admin\Reference\CalendarSystemController;
use App\Http\Controllers\Admin\Reference\EraDateLookupController;
use App\Http\Controllers\Admin\Reference\GeographicRegionController;
use App\Http\Controllers\Admin\Reference\HistoricalPeriodController;
use App\Http\Controllers\Admin\Reference\HistoriographicalSchoolController;
use App\Http\Controllers\Admin\Reference\LanguageFamilyController;
use App\Http\Controllers\Admin\Reference\MeasurementUnitController;
use App\Http\Controllers\Admin\Reference\ReligiousTraditionController;
use App\Http\Controllers\Admin\Reference\SourceTypeDefinitionController;
use App\Http\Controllers\Admin\Reference\WritingSystemController;
use App\Http\Controllers\Admin\RelationshipController;
use App\Http\Controllers\Web\ChronicleController;
use Illuminate\Support\Facades\Route;
use Laravel\Fortify\Features;

Route::inertia('/', 'welcome', [
    'canRegister' => Features::enabled(Features::registration()),
])->name('home');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::inertia('dashboard', 'dashboard')->name('dashboard');

    // Read-only pages are open to any authenticated, verified user.
    // Write verbs are permission-gated; `admin` bypasses via Gate::before.
    Route::get('entities', [EntityController::class, 'index'])->name('entities.index');
    Route::get('entities/create', [EntityController::class, 'create'])->name('entities.create');
    Route::get('entities/{entity}', [EntityController::class, 'show'])->name('entities.show');
    Route::get('entities/{entity}/edit', [EntityController::class, 'edit'])->name('entities.edit');
    Route::middleware('permission:entities.write')->group(function () {
        Route::post('entities', [EntityController::class, 'store'])->name('entities.store');
        Route::put('entities/{entity}', [EntityController::class, 'update'])->name('entities.update');
        Route::delete('entities/{entity}', [EntityController::class, 'destroy'])->name('entities.destroy');
    });

    // ── Relationships (JSON, embedded in entity edit/show pages) ─────────
    Route::get('entities/{entity}/relationships', [RelationshipController::class, 'index'])->name('entities.relationships.index');
    Route::middleware('permission:relationships.write')->group(function () {
        Route::post('entities/{entity}/relationships', [RelationshipController::class, 'store'])->name('entities.relationships.store');
        Route::put('entities/{entity}/relationships/{relationship}', [RelationshipController::class, 'update'])->name('entities.relationships.update');
        Route::delete('entities/{entity}/relationships/{relationship}', [RelationshipController::class, 'destroy'])->name('entities.relationships.destroy');
    });

    // ── Geometry Periods (JSON, embedded in entity edit/show pages) ─
    Route::get('entities/{entity}/geometry-periods', [EntityGeometryPeriodController::class, 'index'])->name('entities.geometry-periods.index');
    Route::get('entities/{entity}/geometry-periods/{geometryPeriod}', [EntityGeometryPeriodController::class, 'show'])->name('entities.geometry-periods.show');
    Route::middleware('permission:geometry.write')->group(function () {
        Route::post('entities/{entity}/geometry-periods', [EntityGeometryPeriodController::class, 'store'])->name('entities.geometry-periods.store');
        Route::put('entities/{entity}/geometry-periods/{geometryPeriod}', [EntityGeometryPeriodController::class, 'update'])->name('entities.geometry-periods.update');
        Route::delete('entities/{entity}/geometry-periods/{geometryPeriod}', [EntityGeometryPeriodController::class, 'destroy'])->name('entities.geometry-periods.destroy');

        // Derive canonical tables (notably territory geometry periods from the
        // primary location) so a just-edited entity becomes map-visible.
        Route::post('entities/{entity}/backfill', [EntityController::class, 'backfill'])->name('entities.backfill');
    });

    // ── Reference Tables ─────────────────────────────────────────────
    Route::get('reference/geographic-regions', [GeographicRegionController::class, 'index'])->name('reference.geographic-regions.index');
    Route::get('reference/historical-periods', [HistoricalPeriodController::class, 'index'])->name('reference.historical-periods.index');
    Route::get('reference/historiographical-schools', [HistoriographicalSchoolController::class, 'index'])->name('reference.historiographical-schools.index');
    Route::get('reference/calendar-systems', [CalendarSystemController::class, 'index'])->name('reference.calendar-systems.index');
    Route::get('reference/era-date-lookup', [EraDateLookupController::class, 'index'])->name('reference.era-date-lookup.index');
    Route::get('reference/writing-systems', [WritingSystemController::class, 'index'])->name('reference.writing-systems.index');
    Route::get('reference/religious-traditions', [ReligiousTraditionController::class, 'index'])->name('reference.religious-traditions.index');
    Route::get('reference/measurement-units', [MeasurementUnitController::class, 'index'])->name('reference.measurement-units.index');
    Route::get('reference/language-families', [LanguageFamilyController::class, 'index'])->name('reference.language-families.index');
    Route::get('reference/source-type-definitions', [SourceTypeDefinitionController::class, 'index'])->name('reference.source-type-definitions.index');

    // ── AI Chat (streaming) ───────────────────────────────────────────────────
    Route::post('ai/chat', [AiChatController::class, 'chat'])->name('ai.chat');

    // ── AI Proposals ─────────────────────────────────────────────────────────
    Route::prefix('ai')->name('ai.')->group(function () {
        Route::post('proposals/{change}/parts/{key}/discard', [AiProposalController::class, 'discard'])->name('proposals.discard');
        Route::middleware('permission:entities.write')->group(function () {
            Route::post('proposals/{change}/parts/{key}/apply', [AiProposalController::class, 'apply'])->name('proposals.apply');
        });
    });

    // ── Chronicles ─────────────────────────────────────────────
    Route::get('/chronicles', [ChronicleController::class, 'index'])->name('chronicles.index');
    Route::get('/chronicles/create', [ChronicleController::class, 'create'])->name('chronicles.create');
    Route::get('/chronicles/{slug}', [ChronicleController::class, 'show'])->name('chronicles.show');
    Route::get('/chronicles/{slug}/edit', [ChronicleController::class, 'edit'])->name('chronicles.edit');
    Route::middleware('permission:chronicles.write')->group(function () {
        Route::post('/chronicles', [ChronicleController::class, 'store'])->name('chronicles.store');
        Route::put('/chronicles/{slug}', [ChronicleController::class, 'update'])->name('chronicles.update');
        Route::delete('/chronicles/{slug}', [ChronicleController::class, 'destroy'])->name('chronicles.destroy');
    });
});

require __DIR__.'/settings.php';
