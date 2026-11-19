<?php

declare(strict_types=1);

namespace App\Actions\Persona;

use App\Models\Entity;
use Illuminate\Support\Facades\Cache;

/** The rendered surroundings briefing of a speaker, cached (the data rarely changes). */
class GetPersonaBriefingAction
{
    public function __construct(private readonly BuildPersonaKnowledgeAction $knowledge) {}

    public function __invoke(Entity $entity, int $knowledgeYear): string
    {
        $budget = (int) config('persona.knowledge.token_budget', 2500);
        $key = "persona:briefing:{$entity->entity_id}:{$knowledgeYear}:{$budget}";

        return Cache::remember(
            $key,
            (int) config('persona.knowledge.cache_seconds', 3600),
            fn () => ($this->knowledge)($entity, $knowledgeYear, $budget)->render(),
        );
    }
}
