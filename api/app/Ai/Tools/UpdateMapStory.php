<?php

declare(strict_types=1);

namespace App\Ai\Tools;

use App\Actions\MapStory\PatchMapStoryAction;
use App\Models\MapStory;
use App\Support\MapStory\JsonPatch;
use App\Support\MapStory\MapStoryFile;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use stdClass;
use Symfony\Component\HttpKernel\Exception\UnprocessableEntityHttpException;

/**
 * Propose an edit to a map story as RFC 6902 JSON Patch ops (add, remove,
 * replace, move, copy, test) on its authored document. The patch is checked
 * when proposed: an op that cannot apply or a patched document with errors
 * rejects the whole patch (nothing is staged, the errors come back);
 * otherwise one part is staged, with a from → to diff per op and the
 * warnings. Applying re-applies the ops to the current document, all or
 * none, and saves a revision whose source is `ai` (PatchMapStoryAction).
 */
class UpdateMapStory extends AgentTool
{
    public function __construct(private PatchMapStoryAction $patch) {}

    public static function name(): string
    {
        return 'update_map_story';
    }

    public function description(): string
    {
        return 'Propose an edit to a map story as JSON Patch ops (RFC 6902: add, remove, replace, move, copy, test) on its document, '
            .'with paths from get_map_story (e.g. /steps/3/narrative, /steps/3/positions/roman-left/at, /units/-). '
            .'The whole patch is checked first: if any op fails or the result has errors, nothing is staged and the errors come back — fix them and resend the whole patch. '
            .'Otherwise the operator reviews and applies it; the result lists warnings to consider. Coordinates are [lon, lat]: get them from the place tools.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'slug' => $schema->string()->description('The story slug (from get_map_story)')->required(),
            'ops' => $schema->array()->items($schema->object(fn (JsonSchema $s) => [
                'op' => $s->string()->enum(JsonPatch::OPS)->required(),
                'path' => $s->string()->description('JSON Pointer, e.g. /steps/2/title; /units/- appends')->required(),
                'from' => $s->string()->description('move/copy only: the source pointer'),
                'value' => $s->anyOf([$s->string(), $s->number(), $s->boolean(), $s->object(), $s->array()])
                    ->description('add/replace/test: the new value (any JSON)'),
            ]))->description('The JSON Patch operations, applied in order, all or none')->required(),
            'note' => $schema->string()->description('One line: what this edit does and why (kept with the revision)'),
        ];
    }

    public function buildParts(array $args): array
    {
        $slug = trim((string) ($args['slug'] ?? ''));
        $story = MapStory::query()->where('slug', $slug)->first()
            ?? throw new ToolArgumentException("No map story with slug '{$slug}'. Use get_map_story to find it.");
        $ops = is_array($args['ops'] ?? null) ? array_values($args['ops']) : [];
        if ($ops === []) {
            throw new ToolArgumentException('Send at least one op in `ops`.');
        }

        $check = ($this->patch)($story, $ops, 'ai', dryRun: true);
        if ($check['errors'] !== []) {
            throw new ToolArgumentException("Patch rejected — nothing staged. Fix these and resend the whole patch:\n- "
                .implode("\n- ", array_slice($check['errors'], 0, 20)));
        }

        $current = MapStoryFile::authored($story->document);
        $note = trim((string) ($args['note'] ?? '')) ?: null;

        return [[
            'key' => 'map_story',
            'tool' => self::name(),
            'payload' => ['slug' => $story->slug, 'ops' => $ops, 'note' => $note],
            'human_diff' => [
                'summary' => "Edit map story '{$story->title}': ".count($ops).' change'.(count($ops) === 1 ? '' : 's').($note ? " — {$note}" : ''),
                'diff' => $this->diff($current, $ops),
                'warnings' => $check['warnings'],
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $story = MapStory::query()->where('slug', $payload['slug'])->firstOrFail();
        $userId = is_numeric($resolved['user_id'] ?? null) ? (int) $resolved['user_id'] : null;
        $result = ($this->patch)($story, $payload['ops'], 'ai', $userId, $payload['note'] ?? null);
        if ($result['errors'] !== []) {
            throw new UnprocessableEntityHttpException('The patch no longer applies to the story as it is now: '.implode(' · ', array_slice($result['errors'], 0, 5)));
        }

        return ['result_id' => $story->story_id, 'summary' => 'Map story updated'];
    }

    /**
     * From → to per op, for the proposal card.
     *
     * @param  list<array<string, mixed>>  $ops
     * @return array<string, array{from: mixed, to: mixed}>
     */
    private function diff(stdClass $current, array $ops): array
    {
        $diff = [];
        foreach ($ops as $i => $op) {
            $path = (string) ($op['path'] ?? '');
            $label = "{$i}. {$op['op']} {$path}";
            $diff[$label] = match ($op['op'] ?? null) {
                'remove' => ['from' => JsonPatch::at($current, $path), 'to' => null],
                'move', 'copy' => ['from' => (string) ($op['from'] ?? ''), 'to' => $path],
                'test' => ['from' => JsonPatch::at($current, $path), 'to' => $op['value'] ?? null],
                default => ['from' => JsonPatch::at($current, $path), 'to' => $op['value'] ?? null],
            };
        }

        return $diff;
    }
}
