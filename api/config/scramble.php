<?php

use Dedoc\Scramble\Http\Middleware\RestrictedDocsAccess;

return [
    /*
     * Your API path. Only routes starting with this path are added to the docs,
     * so the published spec is exactly the public `/api/v1` contract.
     */
    'api_path' => 'api/v1',

    /*
     * Your API domain. By default, the app domain is used.
     */
    'api_domain' => null,

    /*
     * The path where the OpenAPI specification is exported (served at /docs/api.json).
     */
    'export_path' => 'api.json',

    'info' => [
        /*
         * API version.
         */
        'version' => env('API_VERSION', '1.0.0'),

        /*
         * Description rendered on the home page of the API documentation (`/docs/api`).
         */
        'description' => 'history-mapped — the public read API and editorial write API for the interactive historical atlas. Read endpoints are public; write endpoints require authentication and the matching permission.',
    ],

    /*
     * When true, the documentation UI and JSON spec are publicly accessible in every
     * environment. When false (default), non-local environments require the `viewApiDocs`
     * gate (granted to the `admin` role — see AppServiceProvider). Local dev is always open.
     */
    'docs_public' => (bool) env('SCRAMBLE_DOCS_PUBLIC', false),

    /*
     * Customize Stoplight Elements UI.
     */
    'ui' => [
        'title' => 'history-mapped API',
        'theme' => 'light',
        'hide_try_it' => false,
        'hide_schemas' => false,
        'logo' => '',
        'try_it_credentials_policy' => 'include',
        'layout' => 'responsive',
    ],

    /*
     * The list of servers of the API. When `null`, the server URL is derived from
     * `api_path` and `api_domain`.
     */
    'servers' => null,

    'enum_cases_description_strategy' => 'description',

    'enum_cases_names_strategy' => false,

    'flatten_deep_query_parameters' => true,

    'middleware' => [
        'web',
        RestrictedDocsAccess::class,
    ],

    'extensions' => [],
];
