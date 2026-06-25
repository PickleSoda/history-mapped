<?php

namespace App\Ai\Agents;

use App\Ai\Tools\CreateChronicle;
use App\Ai\Tools\CreateChronicleEntry;
use App\Ai\Tools\CreateEntity;
use App\Ai\Tools\CreateRelationship;
use App\Ai\Tools\GetEntityContext;
use App\Ai\Tools\MergeDuplicateEntities;
use App\Ai\Tools\SetEntityLocation;
use App\Ai\Tools\SetEntityWikidata;
use App\Ai\Tools\UpdateChronicleEntry;
use App\Ai\Tools\UpdateEntityFields;
use App\Ai\Tools\VerifyWikidata;
use App\Models\User;
use Laravel\Ai\Concerns\RemembersConversations;
use Laravel\Ai\Contracts\Agent;
use Laravel\Ai\Contracts\Conversational;
use Laravel\Ai\Contracts\HasTools;
use Laravel\Ai\Promptable;

class GlobalAgent implements Agent, Conversational, HasTools
{
    use Promptable, RemembersConversations;

    /**
     * @param  array{user_id:string,context_type:string,context_id:string,conversation_id:?string}  $context
     */
    public function __construct(
        public User $user,
        public array $context = [],
    ) {}

    public function instructions(): string
    {
        return view('ai.instructions.global')->render();
    }

    /**
     * Full registered toolset.
     *
     * Read-only tools (VerifyWikidata, GetEntityContext) need no context — they
     * never stage proposals. Staging tools receive $this->context so ProposedChange
     * rows carry the correct user, conversation, and global context.
     */
    public function tools(): iterable
    {
        return [
            // Read-only / lookup
            app(VerifyWikidata::class),
            app(GetEntityContext::class),

            // Staging — create
            app(CreateEntity::class)->withContext($this->context),
            app(CreateChronicle::class)->withContext($this->context),
            app(CreateChronicleEntry::class)->withContext($this->context),

            // Staging — edit
            app(UpdateEntityFields::class)->withContext($this->context),
            app(SetEntityLocation::class)->withContext($this->context),
            app(SetEntityWikidata::class)->withContext($this->context),
            app(CreateRelationship::class)->withContext($this->context),
            app(UpdateChronicleEntry::class)->withContext($this->context),
            app(MergeDuplicateEntities::class)->withContext($this->context),
        ];
    }
}
