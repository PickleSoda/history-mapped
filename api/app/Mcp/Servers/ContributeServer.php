<?php

declare(strict_types=1);

namespace App\Mcp\Servers;

use App\Mcp\Resources\ConnectionsApp;
use App\Mcp\Resources\EntityCardApp;
use App\Mcp\Resources\TimelineApp;
use App\Mcp\Resources\YearMapApp;
use App\Mcp\Tools\Contribute\MyContributions;
use App\Mcp\Tools\Contribute\ProposeEntity;
use App\Mcp\Tools\Contribute\ProposeRelationship;
use App\Mcp\Tools\Contribute\SuggestCorrection;
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
 * The signed-in MCP server at /mcp/contribute (OAuth 2.1 via Passport). It
 * serves everything the public server does, and, to accounts that may
 * contribute, tools that record corrections and new-record proposals. Every
 * write is a `contributions` row a moderator reviews in the admin; no tool
 * writes to the atlas directly or deletes anything.
 */
#[Name('History Mapped (contribute)')]
#[Version('1.0.0')]
#[Instructions(<<<'TXT'
History Mapped is an interactive historical atlas: about 640,000 entities (people, polities, settlements, battles, wars, treaties, monuments, works, movements and more, 30 types) with dates, places, relationships and narrative chronicles, drawn mostly from Wikidata and Wikipedia.

READING
- Years are signed integers: 1066 is AD 1066, -44 is 44 BC. There is no year 0.
- Start with search-atlas to find ids, then get-entity, get-connections or what-was-happening. Chronicles are curated narratives: find-chronicles, then get-chronicle.
- Every record has an atlas_url. Cite it when you use the record. Most records were imported automatically and are unreviewed (verification_status): say so when a claim rests on one.

CONTRIBUTING (signed-in users who may contribute)
- suggest-correction, propose-entity and propose-relationship never change the atlas. Each records a proposal that a moderator reviews; only an approved one becomes real. Say so to the user: "I have proposed this; a moderator will review it."
- Always look before you propose: search-atlas for the entity, get-connections for the relationship. Do not propose what exists.
- Propose only what you can source. Give sources and a note for the moderator; do not invent facts, dates or coordinates.
- Confirm with the user before each call; these tools write proposals under their account.
- To add an entity and link it: propose-entity, then propose-relationship using the contribution_id it returned. Check my-contributions for what was decided.
TXT)]
class ContributeServer extends Server
{
    /**
     * The six read tools of the public server, plus the contribution tools
     * (each registers itself only for accounts with contributions.create).
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
        SuggestCorrection::class,
        ProposeEntity::class,
        ProposeRelationship::class,
        MyContributions::class,
    ];

    /**
     * The same ui:// views as the public server.
     *
     * @var array<int, class-string<Server\Resource>>
     */
    protected array $resources = [
        EntityCardApp::class,
        YearMapApp::class,
        ConnectionsApp::class,
        TimelineApp::class,
    ];

    protected array $prompts = [];
}
