<?php

/*
|--------------------------------------------------------------------------
| Public site pages rendered by the app
|--------------------------------------------------------------------------
|
| The public site is a JavaScript application: its index.html is an empty
| shell. For entity and chronicle pages the app returns that same shell with
| the page's title, description and text filled in, so crawlers that run no
| JavaScript can read them, and it serves the sitemap. Routes:
| routes/site.php; docs/architecture/frontend-app.md, "What crawlers see".
|
*/

return [

    // The built SPA's index.html. On the hosted site the app container mounts
    // the web_dist volume read-only, where Caddy serves /srv/web/current.
    // When the file is not there the page routes answer 503 and Caddy falls
    // back to the plain shell.
    'shell_path' => env('SITE_SHELL_PATH', '/srv/web/current/index.html'),

    // Page and sitemap requests a minute for one client address. A visitor
    // loads one such page per visit (the web app handles the rest), so this
    // only paces crawlers: a typical page costs about as much as one API call.
    'rate_limit' => (int) env('SITE_RATE_LIMIT', 120),

    // How long crawlers may keep a sitemap file, in seconds.
    'sitemap_max_age' => (int) env('SITE_SITEMAP_MAX_AGE', 21600),

    // Most connections listed on an entity page.
    'connections' => 40,

];
