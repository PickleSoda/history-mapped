<?php

declare(strict_types=1);

namespace App\Mcp\Tools\Contribute;

use App\Models\User;
use Laravel\Mcp\Request;
use Laravel\Mcp\Server\Tool;
use Laravel\Passport\Passport;

/**
 * Base for the tools of /mcp/contribute that write: shown only to signed-in
 * accounts that may contribute (`contributions.create`, the same permission as
 * the atlas's "Suggest edit"). These tools are not read-only, so the MCP host
 * asks before each call; they only ever record proposals for review.
 */
abstract class ContributeTool extends Tool
{
    public function shouldRegister(Request $request): bool
    {
        return $request->user()?->can('contributions.create') ?? false;
    }

    protected function account(Request $request): User
    {
        $user = $request->user();
        abort_unless($user instanceof User && $user->can('contributions.create'), 403, 'This account cannot contribute.');

        return $user;
    }

    /** The connecting app's name as it registered with OAuth ("Claude"), recorded on each proposal. */
    protected function clientName(User $user): string
    {
        $clientId = $user->token()?->oauth_client_id ?? null;
        $name = $clientId === null ? null : Passport::client()->newQuery()->whereKey($clientId)->value('name');

        return mb_substr((string) ($name ?: 'MCP client'), 0, 255);
    }
}
