<?php

declare(strict_types=1);

namespace App\Enums;

/** Where a contribution was submitted from. */
enum ContributionSource: string
{
    /** The public atlas (web SPA). */
    case Atlas = 'atlas';

    /** An MCP client (Claude) connected to /mcp/contribute. */
    case Mcp = 'mcp';
}
