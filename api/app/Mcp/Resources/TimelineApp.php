<?php

declare(strict_types=1);

namespace App\Mcp\Resources;

use Laravel\Mcp\Request;
use Laravel\Mcp\Response;
use Laravel\Mcp\Server\AppResource;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Attributes\Title;

#[Title('Chronicle timeline')]
#[Description('The entries of a chronicle on a time axis.')]
class TimelineApp extends AppResource
{
    public function handle(Request $request): Response
    {
        return Response::view('mcp.timeline-app', ['title' => $this->title()]);
    }
}
