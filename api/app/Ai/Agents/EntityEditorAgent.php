<?php

namespace App\Ai\Agents;

use App\Ai\Tools\CreateEntity;
use App\Ai\Tools\CreateRelationship;
use App\Ai\Tools\GetEntityContext;
use App\Ai\Tools\MergeDuplicateEntities;
use App\Ai\Tools\SetEntityLocation;
use App\Ai\Tools\SetEntityWikidata;
use App\Ai\Tools\UpdateEntityFields;
use App\Ai\Tools\VerifyWikidata;
use App\Models\Entity;
use App\Models\User;
use Laravel\Ai\Concerns\RemembersConversations;
use Laravel\Ai\Contracts\Agent;
use Laravel\Ai\Contracts\Conversational;
use Laravel\Ai\Contracts\HasTools;
use Laravel\Ai\Promptable;

class EntityEditorAgent implements Agent, Conversational, HasTools
{
    use Promptable, RemembersConversations;

    /**
     * @param  array{user_id:string,context_type:string,context_id:string,conversation_id:?string}  $context
     */
    public function __construct(
        public Entity $entity,
        public User $user,
        public array $context = [],
    ) {}

    /**
     * Render the system instructions from the Blade template with live entity state.
     */
    public function instructions(): string
    {
        return view('ai.instructions.entity-editor', [
            'entity' => $this->entity->loadMissing([
                'primaryLocation',
                'primaryTemporalRange',
                'outgoingRelationships.targetEntity',
                'incomingRelationships.sourceEntity',
            ]),
        ])->render();
    }

    /**
     * Return all tools available to this agent.
     * Read-only tools (GetEntityContext, VerifyWikidata) do not need context.
     * Staging tools receive $this->context so ProposedChange is attributed correctly.
     */
    public function tools(): iterable
    {
        return [
            app(GetEntityContext::class)->forEntity($this->entity),
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
