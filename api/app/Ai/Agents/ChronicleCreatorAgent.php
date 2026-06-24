<?php

namespace App\Ai\Agents;

use App\Ai\Tools\CreateChronicle;
use App\Models\User;
use Laravel\Ai\Concerns\RemembersConversations;
use Laravel\Ai\Contracts\Agent;
use Laravel\Ai\Contracts\Conversational;
use Laravel\Ai\Contracts\HasTools;
use Laravel\Ai\Promptable;

class ChronicleCreatorAgent implements Agent, Conversational, HasTools
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
        return view('ai.instructions.chronicle-creator')->render();
    }

    /**
     * Return creation-only tools.
     * Staging tool receives $this->context so ProposedChange is attributed correctly.
     */
    public function tools(): iterable
    {
        return [
            app(CreateChronicle::class)->withContext($this->context),
        ];
    }
}
