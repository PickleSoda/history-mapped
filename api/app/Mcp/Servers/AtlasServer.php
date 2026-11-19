<?php

declare(strict_types=1);

namespace App\Mcp\Servers;

use App\Mcp\Tools\FindChronicles;
use App\Mcp\Tools\GetChronicle;
use App\Mcp\Tools\GetConnections;
use App\Mcp\Tools\GetEntity;
use App\Mcp\Tools\SearchAtlas;
use App\Mcp\Tools\WhatWasHappening;
use Laravel\Mcp\Server;
use Laravel\Mcp\Server\Attributes\Instructions;
use Laravel\Mcp\Server\Attributes\Name;
use Laravel\Mcp\Server\Attributes\Version;

/**
 * The public, read-only MCP server at /mcp. Claude (or any MCP host) adds it
 * as a connector without sign-in. Every tool reads the same public data as
 * the atlas, capped; views (ui:// app resources) render results in the chat.
 */
#[Name('History Mapped')]
#[Version('1.0.0')]
#[Instructions(<<<'TXT'
History Mapped is an interactive historical atlas: about 640,000 entities (people, polities, settlements, battles, wars, treaties, monuments, works, movements and more, 30 types) with dates, places, relationships and narrative chronicles, drawn mostly from Wikidata and Wikipedia.

- Years are signed integers: 1066 is AD 1066, -44 is 44 BC. There is no year 0.
- Results are capped and ranked (by similarity for searches, by historical impact otherwise). Ask for a narrower year, place or type rather than assuming the list is complete.
- Start with search-atlas to find ids, then get-entity, get-connections or what-was-happening. Chronicles are curated narratives: find-chronicles, then get-chronicle.
- Every record has an atlas_url. Cite it when you use the record so the reader can open it on the map.
- Data quality varies: most records were imported automatically and are unreviewed (verification_status). Say so when a claim rests on one.
TXT)]
class AtlasServer extends Server
{
    /**
     * Read tools (owned by app/Mcp/Tools).
     *
     * @var array<int, class-string<Server\Tool>>
     */
    protected array $tools = [
        SearchAtlas::class,
        GetEntity::class,
        WhatWasHappening::class,
        GetConnections::class,
        FindChronicles::class,
        GetChronicle::class,
    ];

    /**
     * ui:// views (owned by app/Mcp/Resources).
     *
     * @var array<int, class-string<Server\Resource>>
     */
    protected array $resources = [
        // VIEWS
    ];

    protected array $prompts = [];
}
