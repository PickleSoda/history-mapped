<?php

declare(strict_types=1);

namespace App\Support\Persona;

/**
 * The surroundings briefing of one speaker: what a person of their standing
 * would plausibly know about their time and place. Built without an LLM by
 * BuildPersonaKnowledgeAction; rendered as compact text within a token budget.
 *
 * Sections are in priority order; when the text is over budget the last lines
 * of the lowest-priority section go first.
 */
final class PersonaKnowledge
{
    public const SECTION_TITLES = [
        'relations' => 'Their own life and people',
        'domain' => 'Their realm: allies, enemies, wars',
        'nearby' => 'Around them in their lifetime',
        'chronicle' => 'Remembered episodes',
        'contemporaries' => 'Famous contemporaries',
    ];

    /**
     * @param  array<string, list<string>>  $sections  key => lines
     * @param  array<string, mixed>  $stats
     */
    public function __construct(
        public readonly int $knowledgeYear,
        public readonly ?int $birthYear,
        public readonly string $reach,
        public array $sections,
        public readonly array $stats = [],
    ) {}

    public static function formatYear(int $year): string
    {
        return $year < 0 ? abs($year).' BCE' : (string) $year;
    }

    /** About four characters a token; good enough for a budget. */
    public static function estimateTokens(string $text): int
    {
        return (int) ceil(mb_strlen($text) / 4);
    }

    public function lineCount(): int
    {
        return array_sum(array_map('count', $this->sections));
    }

    public function isEmpty(): bool
    {
        return $this->lineCount() === 0;
    }

    /** Drop the lowest-priority lines until the text fits `$tokenBudget`. */
    public function fit(int $tokenBudget): self
    {
        $order = array_reverse(array_keys(self::SECTION_TITLES));
        while (self::estimateTokens($this->render()) > $tokenBudget) {
            $trimmed = false;
            foreach ($order as $key) {
                if (! empty($this->sections[$key])) {
                    array_pop($this->sections[$key]);
                    $trimmed = true;
                    break;
                }
            }
            if (! $trimmed) {
                break;
            }
        }

        return $this;
    }

    public function render(): string
    {
        $out = [];
        foreach (self::SECTION_TITLES as $key => $title) {
            $lines = $this->sections[$key] ?? [];
            if ($lines === []) {
                continue;
            }
            $out[] = $title.':';
            foreach ($lines as $line) {
                $out[] = '- '.$line;
            }
            $out[] = '';
        }

        return rtrim(implode("\n", $out));
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return [
            'knowledge_year' => $this->knowledgeYear,
            'birth_year' => $this->birthYear,
            'reach' => $this->reach,
            'sections' => $this->sections,
            'stats' => $this->stats,
        ];
    }
}
