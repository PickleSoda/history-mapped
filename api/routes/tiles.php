<?php

use App\Http\Tiles\TileController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| Vector tiles served by the app (TILES_DRIVER=app)
|--------------------------------------------------------------------------
|
| Mounted at /tiles by bootstrap/app.php: the same paths Martin answers under
| its `route_prefix: /tiles`, so Caddy can send /tiles/* to either one. Public,
| uncredentialed GETs: no session, CSRF or API throttle, and the responses
| carry an open CORS header like Martin's.
|
*/

Route::get('/catalog', [TileController::class, 'catalog'])->name('tiles.catalog');

Route::get('/{source}', [TileController::class, 'tileJson'])
    ->where('source', '[a-z0-9_]+')
    ->name('tiles.tilejson');

Route::get('/{source}/{z}/{x}/{y}', [TileController::class, 'tile'])
    ->where(['source' => '[a-z0-9_]+', 'z' => '[0-9]{1,2}', 'x' => '[0-9]{1,10}', 'y' => '[0-9]{1,10}'])
    ->name('tiles.tile');
