<?php

namespace App\Ai\Agents;

use App\Ai\Tools\CreateEntity;
use App\Ai\Tools\CreateRelationship;
use App\Ai\Tools\MergeDuplicateEntities;
use App\Ai\Tools\SetEntityLocation;
use App\Ai\Tools\SetEntityWikidata;
use App\Ai\Tools\UpdateEntityFields;
use App\Ai\Tools\VerifyWikidata;
use App\Models\Chronicle;
use App\Models\User;
use Laravel\Ai\Concerns\RemembersConversations;
use Laravel\Ai\Contracts\Agent;
use Laravel\Ai\Contracts\Conversational;
use Laravel\Ai\Contracts\HasTools;
use Laravel\Ai\Promptable;

class ChronicleEditorAgent implements Agent, Conversational, HasTools
{
    use Promptable, RemembersConversations;

    /**
     * @param  array{user_id:string,context_type:string,context_id:string,conversation_id:?string}  $context
     */
    public function __construct(
        public Chronicle $chronicle,
        public User $user,
        public array $context = [],
    ) {}

    /**
     * Render the system instructions from the Blade template with live chronicle state.
     * Loads entries and their referenced entities (DISTINCT by entity_id).
     */
    public function instructions(): string
    {
        $chronicle = $this->chronicle->loadMissing(['entries']);

        // Eager-load secondaryEntities on each entry to avoid N+1 queries.
        $chronicle->entries->load('secondaryEntities');

        // Collect DISTINCT entities referenced across all entries.
        $entities = $chronicle->entries
            ->flatMap(fn ($entry) => $entry->secondaryEntities)
            ->unique('entity_id')
            ->values();

        return view('ai.instructions.chronicle-editor', [
            'chronicle' => $chronicle,
            'entities' => $entities,
        ])->render();
    }

    /**
     * Return all tools available to this agent.
     * Read-only tool (VerifyWikidata) does not need context.
     * Staging tools receive $this->context so ProposedChange is attributed correctly.
     */
    public function tools(): iterable
    {
        return [
            app(VerifyWikidata::class),
            app(CreateEntity::class)->withContext($this->context),
            app(SetEntityLocation::class)->withContext($this->context),
            app(UpdateEntityFields::class)->withContext($this->context),
            app(SetEntityWikidata::class)->withContext($this->context),
            app(CreateRelationship::class)->withContext($this->context),
            app(MergeDuplicateEntities::class)->withContext($this->context),
        ];
    }
}
