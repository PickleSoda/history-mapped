<?php

declare(strict_types=1);

use App\Mcp\Servers\AtlasServer;
use App\Mcp\Servers\ContributeServer;
use Illuminate\Support\Facades\Route;
use Laravel\Mcp\Facades\Mcp;
use Laravel\Mcp\Server\Http\Controllers\OAuthRegisterController;

/*
| MCP servers (laravel/mcp). Loaded by the package with no middleware group:
| no session, no CSRF. See docs/architecture/mcp-connector.md.
*/

// Public, read-only: Claude adds it as a custom connector without sign-in.
Mcp::web('/mcp', AtlasServer::class)
    ->middleware('throttle:mcp')
    ->name('mcp.atlas');

// OAuth 2.1 discovery (Passport). Dynamic client registration is public by design (RFC 7591) and
// each call writes an oauth_clients row, so it is registered here with its own per-IP limit.
Mcp::oauthRoutes(registration: false);
Route::post('oauth/register', OAuthRegisterController::class)
    ->middleware('throttle:10,1')
    ->name('mcp.oauth.register');

// Signed-in contributors: reads plus proposals that a moderator reviews in the admin.
Mcp::web('/mcp/contribute', ContributeServer::class)
    ->middleware(['auth:api', 'throttle:mcp'])
    ->name('mcp.contribute');
