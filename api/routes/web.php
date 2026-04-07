<?php

use App\Http\Controllers\Admin\EntityController;
use App\Http\Controllers\Admin\GeometrySnapshotController;
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
use Illuminate\Support\Facades\Route;
use Laravel\Fortify\Features;

Route::inertia('/', 'welcome', [
    'canRegister' => Features::enabled(Features::registration()),
])->name('home');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::inertia('dashboard', 'dashboard')->name('dashboard');

    Route::get('entities', [EntityController::class, 'index'])->name('entities.index');
    Route::get('entities/create', [EntityController::class, 'create'])->name('entities.create');
    Route::post('entities', [EntityController::class, 'store'])->name('entities.store');
    Route::get('entities/{entity}', [EntityController::class, 'show'])->name('entities.show');
    Route::get('entities/{entity}/edit', [EntityController::class, 'edit'])->name('entities.edit');
    Route::put('entities/{entity}', [EntityController::class, 'update'])->name('entities.update');
    Route::delete('entities/{entity}', [EntityController::class, 'destroy'])->name('entities.destroy');

    // ── Relationships (JSON, embedded in entity edit/show pages) ─────────
    Route::get('entities/{entity}/relationships', [RelationshipController::class, 'index'])->name('entities.relationships.index');
    Route::post('entities/{entity}/relationships', [RelationshipController::class, 'store'])->name('entities.relationships.store');
    Route::delete('entities/{entity}/relationships/{relationship}', [RelationshipController::class, 'destroy'])->name('entities.relationships.destroy');

    // ── Geometry Snapshot Compatibility (JSON adapter over geometry periods) ──
    Route::get('entities/{entity}/geometry-snapshots', [GeometrySnapshotController::class, 'index'])->name('entities.geometry-snapshots.index');
    Route::post('entities/{entity}/geometry-snapshots', [GeometrySnapshotController::class, 'store'])->name('entities.geometry-snapshots.store');
    Route::put('entities/{entity}/geometry-snapshots/{snapshot}', [GeometrySnapshotController::class, 'update'])->name('entities.geometry-snapshots.update');
    Route::delete('entities/{entity}/geometry-snapshots/{snapshot}', [GeometrySnapshotController::class, 'destroy'])->name('entities.geometry-snapshots.destroy');

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
});

require __DIR__.'/settings.php';
