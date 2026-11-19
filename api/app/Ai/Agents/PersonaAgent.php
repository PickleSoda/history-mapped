<?php

namespace App\Ai\Agents;

use Laravel\Ai\Contracts\Agent;
use Laravel\Ai\Contracts\Conversational;
use Laravel\Ai\Messages\Message;
use Laravel\Ai\Promptable;

/**
 * One in-character reply: the assembled system prompt, the earlier turns, no
 * tools (a speaker answers from the briefing, it never looks things up).
 *
 * Subclasses (PersonaWriterAgent, PersonaSummaryAgent) differ only in name, so
 * tests can fake each separately.
 */
class PersonaAgent implements Agent, Conversational
{
    use Promptable;

    /** @param  list<Message>  $history */
    public function __construct(
        private readonly string $system,
        private readonly array $history = [],
        private readonly ?string $modelName = null,
        private readonly int $maxOutputTokens = 450,
        private readonly float $temp = 0.8,
    ) {}

    public function instructions(): string
    {
        return $this->system;
    }

    public function messages(): iterable
    {
        return $this->history;
    }

    public function model(): ?string
    {
        return $this->modelName;
    }

    public function maxTokens(): int
    {
        return $this->maxOutputTokens;
    }

    public function temperature(): float
    {
        return $this->temp;
    }

    public function timeout(): int
    {
        return (int) config('persona.limits.timeout', 60);
    }
}
