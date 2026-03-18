<?php

use App\Http\Controllers\Admin\EntityController;
use Illuminate\Support\Facades\Route;
use Laravel\Fortify\Features;

Route::inertia('/', 'welcome', [
    'canRegister' => Features::enabled(Features::registration()),
])->name('home');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::inertia('dashboard', 'dashboard')->name('dashboard');

    Route::get('entities', [EntityController::class, 'index'])->name('entities.index');
    Route::get('entities/{entity}', [EntityController::class, 'show'])->name('entities.show');
});

require __DIR__.'/settings.php';
