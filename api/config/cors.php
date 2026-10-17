<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Cross-Origin Resource Sharing (CORS) Configuration
    |--------------------------------------------------------------------------
    |
    | Settings for cross-origin resource sharing. The web/ SPA needs to hit
    | the API and Sanctum cookie endpoints from a different origin.
    |
    */

    // Fortify's JSON auth endpoints are called cross-origin by the SPA too.
    'paths' => [
        'api/*', 'sanctum/csrf-cookie',
        'login', 'logout', 'register', 'two-factor-challenge', 'forgot-password',
    ],

    'allowed_methods' => ['*'],

    'allowed_origins' => [env('FRONTEND_URL', 'http://localhost:5173')],

    'allowed_origins_patterns' => [],

    'allowed_headers' => ['*'],

    'exposed_headers' => [],

    'max_age' => 0,

    'supports_credentials' => true,

];
