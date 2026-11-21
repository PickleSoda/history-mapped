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

    // How long a browser may remember the answer to a preflight (seconds).
    // At 0 it asked again before every single write. Two hours is the most
    // Chrome keeps one; the SPA's reads need no preflight at all (they carry
    // no custom header, see web/src/lib/api/client.ts).
    'max_age' => 7200,

    'supports_credentials' => true,

];
