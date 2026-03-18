<?php

use App\Providers\AppServiceProvider;
use App\Providers\FortifyServiceProvider;
use App\Support\Database\PostgisServiceProvider;

return [
    AppServiceProvider::class,
    FortifyServiceProvider::class,
    PostgisServiceProvider::class,
];
