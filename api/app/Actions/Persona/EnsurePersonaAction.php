<?php

declare(strict_types=1);

namespace App\Actions\Persona;

use App\Ai\Agents\PersonaWriterAgent;
use App\Exceptions\Persona\PersonaException;
use App\Models\Entity;
use App\Models\EntityPersona;
use App\Support\Persona\PersonaKnowledge;
use App\Support\Persona\SpeakerEligibility;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * The stored persona of a speaker, written once by the LLM from the entity's
 * own atlas data the first time someone talks to them. A persona edited by
 * hand (`source = edited`) is never regenerated; a generated one is rewritten
 * when `persona.persona_version` is raised.
 */
class EnsurePersonaAction
{
    public function __construct(private readonly BuildPersonaKnowledgeAction $knowledge) {}

    public function __invoke(Entity $entity): EntityPersona
    {
        $version = (int) config('persona.persona_version', 1);
        $current = EntityPersona::where('entity_id', $entity->entity_id)->first();
        if ($current && ($current->source === 'edited' || $current->version >= $version)) {
            return $current;
        }

        $lock = Cache::lock('persona:generate:'.$entity->entity_id, 120);
        try {
            $lock->block(40);
        } catch (Throwable) {
            throw PersonaException::busy();
        }
        try {
            // Someone else may have written it while this request waited.
            $current = EntityPersona::where('entity_id', $entity->entity_id)->first();
            if ($current && ($current->source === 'edited' || $current->version >= $version)) {
                return $current;
            }

            return $this->generate($entity, $current, $version);
        } finally {
            $lock->release();
        }
    }

    private function generate(Entity $entity, ?EntityPersona $existing, int $version): EntityPersona
    {
        $death = SpeakerEligibility::deathYear($entity);
        $knowledgeYear = $existing?->knowledge_year ?? $death;
        if ($knowledgeYear === null) {
            throw PersonaException::notTalkable();
        }

        $briefing = ($this->knowledge)($entity, $knowledgeYear, 700);
        $model = config('persona.writer_model') ?: config('persona.chat_model');

        try {
            $response = (new PersonaWriterAgent(
                $this->instructions(),
                [],
                $model,
                900,
                0.4,
            ))->prompt($this->facts($entity, $knowledgeYear, $briefing), model: $model);
            $persona = $this->parse((string) $response->text);
        } catch (Throwable $e) {
            Log::warning('persona.generate_failed', ['entity' => $entity->entity_id, 'error' => $e->getMessage()]);
            throw PersonaException::providerFailed();
        }

        return EntityPersona::updateOrCreate(
            ['entity_id' => $entity->entity_id],
            [
                'persona' => $persona,
                'knowledge_year' => $knowledgeYear,
                'model' => $model ?: config('ai.providers.'.config('ai.default').'.models.text.default'),
                'version' => $version,
                'source' => 'generated',
            ],
        );
    }

    private function instructions(): string
    {
        return <<<'TXT'
You write character sheets for a historical atlas's role-play feature. You are given the atlas's own data about one historical person. Write a compact character sheet that a role-player can use to speak as them.

Rules:
- Use ONLY the supplied facts plus general, well-established knowledge of the period and culture. Do not invent biography: no invented events, relatives, quotations, dates or places.
- Personality and manner may be inferred from the person's role, era and culture, in cautious general terms ("a blunt soldier's directness") rather than claimed as documented fact.
- Keep every item short (under 25 words). No modern idioms.
- Reply with one JSON object and nothing else (no code fence), with exactly these keys:
  "voice": string, how they speak: register, rhythm, diction, typical sentence shape
  "temperament": array of 3-5 short strings
  "values": array of 3-5 short strings
  "cares_about": array of 3-5 short strings, drawn from the supplied facts
  "speech_habits": array of 2-4 short strings (turns of phrase in general terms, not quotations)
  "self_view": string, how they likely see themselves and their place
  "address_to_acquaintance": string, how they address a visitor who has become an acquaintance
  "language_note": string, answer in the visitor's language with period flavour; any language of origin only as a light touch
TXT;
    }

    private function facts(Entity $entity, int $knowledgeYear, PersonaKnowledge $briefing): string
    {
        $range = $entity->primaryTemporalRange;
        $attrs = $entity->attributes ?? [];
        $lines = ['Name: '.$entity->name];
        if ($range) {
            $lines[] = 'Lived: '.($range->start_year !== null ? PersonaKnowledge::formatYear($range->start_year) : '?').' to '.PersonaKnowledge::formatYear($knowledgeYear);
        }
        if (is_array($attrs['roles'] ?? null)) {
            $lines[] = 'Roles: '.implode(', ', array_slice(array_map('strval', array_filter($attrs['roles'], 'is_scalar')), 0, 8));
        }
        if ($entity->summary) {
            $lines[] = 'Summary: '.mb_substr($entity->summary, 0, 600);
        }
        if ($entity->description) {
            $lines[] = 'Description: '.mb_substr($entity->description, 0, 1500);
        } elseif (! empty($attrs['_wikipedia_extract']) && is_string($attrs['_wikipedia_extract'])) {
            $lines[] = 'Encyclopedia lead: '.mb_substr($attrs['_wikipedia_extract'], 0, 900);
        }
        $rel = $briefing->sections['relations'] ?? [];
        if ($rel !== []) {
            $lines[] = "Links in the atlas:\n- ".implode("\n- ", array_slice($rel, 0, 10));
        }

        return implode("\n", $lines);
    }

    /** @return array<string, mixed> */
    private function parse(string $text): array
    {
        $text = trim($text);
        $text = preg_replace('/^```(?:json)?\s*|\s*```$/i', '', $text) ?? $text;
        $start = strpos($text, '{');
        $end = strrpos($text, '}');
        if ($start === false || $end === false) {
            throw new \RuntimeException('No JSON in persona reply.');
        }
        $data = json_decode(substr($text, $start, $end - $start + 1), true);
        if (! is_array($data) || empty($data['voice'])) {
            throw new \RuntimeException('Persona JSON missing voice.');
        }

        $list = fn ($v) => is_array($v) ? array_values(array_filter(array_map(fn ($s) => is_scalar($s) ? mb_substr(trim((string) $s), 0, 200) : null, $v))) : [];
        $str = fn ($v) => is_scalar($v) ? mb_substr(trim((string) $v), 0, 400) : null;

        return array_filter([
            'voice' => $str($data['voice']),
            'temperament' => $list($data['temperament'] ?? []),
            'values' => $list($data['values'] ?? []),
            'cares_about' => $list($data['cares_about'] ?? []),
            'speech_habits' => $list($data['speech_habits'] ?? []),
            'self_view' => $str($data['self_view'] ?? null),
            'address_to_acquaintance' => $str($data['address_to_acquaintance'] ?? null),
            'language_note' => $str($data['language_note'] ?? null),
        ], fn ($v) => $v !== null && $v !== []);
    }
}
