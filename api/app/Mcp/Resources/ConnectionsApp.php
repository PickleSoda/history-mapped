<?php

declare(strict_types=1);

namespace App\Mcp\Resources;

use Laravel\Mcp\Request;
use Laravel\Mcp\Response;
use Laravel\Mcp\Server\AppResource;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Attributes\Title;

#[Title('Connections graph')]
#[Description('An entity and the entities it is connected to, as a radial graph.')]
class ConnectionsApp extends AppResource
{
    public function handle(Request $request): Response
    {
        return Response::view('mcp.connections-app', ['title' => $this->title()]);
    }
}
