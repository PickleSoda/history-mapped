<?php

declare(strict_types=1);

namespace App\Mcp\Resources;

use Laravel\Mcp\Request;
use Laravel\Mcp\Response;
use Laravel\Mcp\Server\AppResource;
use Laravel\Mcp\Server\Attributes\AppMeta;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Attributes\Title;

#[Title('Entity card')]
#[Description('An atlas entity as a card: image with credit, dates, place, summary and its main relationships.')]
#[AppMeta(resourceDomains: ['https://upload.wikimedia.org', 'https://thumb.wikimedia.org'])]
class EntityCardApp extends AppResource
{
    public function handle(Request $request): Response
    {
        return Response::view('mcp.entity-card-app', ['title' => $this->title()]);
    }
}
