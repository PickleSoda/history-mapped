<?php

declare(strict_types=1);

namespace App\Mcp\Resources;

use Laravel\Mcp\Request;
use Laravel\Mcp\Response;
use Laravel\Mcp\Server\AppResource;
use Laravel\Mcp\Server\Attributes\AppMeta;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Attributes\Title;

#[Title('Map at a year')]
#[Description('The entities mapped in a year over the historical borders of that year.')]
#[AppMeta(resourceDomains: ['https://cdnjs.cloudflare.com'], connectDomains: ['https://www.openhistoricalmap.org', 'https://vtiles.openhistoricalmap.org'])]
class YearMapApp extends AppResource
{
    public function handle(Request $request): Response
    {
        return Response::view('mcp.year-map-app', ['title' => $this->title()]);
    }
}
