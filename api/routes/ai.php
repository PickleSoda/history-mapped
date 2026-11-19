<?php

declare(strict_types=1);

use App\Mcp\Servers\AtlasServer;
use Laravel\Mcp\Facades\Mcp;

/*
| MCP servers (laravel/mcp). Loaded by the package with no middleware group:
| no session, no CSRF. See docs/architecture/mcp-connector.md.
*/

// Public, read-only: Claude adds it as a custom connector without sign-in.
Mcp::web('/mcp', AtlasServer::class)
    ->middleware('throttle:mcp')
    ->name('mcp.atlas');
