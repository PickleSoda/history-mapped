<?php

namespace App\Ai\Agents;

use App\Ai\Tools\CreateEntity;
use App\Ai\Tools\VerifyWikidata;
use App\Models\User;
use Laravel\Ai\Concerns\RemembersConversations;
use Laravel\Ai\Contracts\Agent;
use Laravel\Ai\Contracts\Conversational;
use Laravel\Ai\Contracts\HasTools;
use Laravel\Ai\Promptable;

class EntityCreatorAgent implements Agent, Conversational, HasTools
{
    use Promptable, RemembersConversations;

    /**
     * @param  array{user_id:string,context_type:string,context_id:string,conversation_id:?string}  $context
     */
    public function __construct(public User $user, public array $context = []) {}

    /**
     * Render the system instructions from the Blade template.
     */
    public function instructions(): string
    {
        return view('ai.instructions.entity-creator')->render();
    }

    /**
     * Return creation-only tools.
     * Staging tools receive $this->context so ProposedChange is attributed correctly.
     * VerifyWikidata is read-only and does not need context.
     */
    public function tools(): iterable
    {
        return [
            app(CreateEntity::class)->withContext($this->context),
            app(VerifyWikidata::class),
        ];
    }
}
