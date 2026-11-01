<?php

declare(strict_types=1);

namespace App\Ai\Tools;

use App\Actions\MapStory\CheckMapStoryAction;
use App\Ai\Tools\Concerns\FindsMapStory;
use App\Models\MapStory;
use App\Support\MapStory\MapStoryFile;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Ai\Tools\Request;
use LogicException;
use stdClass;
use Stringable;

/**
 * Check a map story without saving: the stored one (`slug`) or an inline
 * `document`. Errors block a save; warnings (a unit jumping with no arrow, a
 * point far from the rest, a ship on land, text lengths…) do not. Read-only.
 */
class ValidateMapStory extends AgentTool
{
    use FindsMapStory;

    public function __construct(private CheckMapStoryAction $check) {}

    public static function name(): string
    {
        return 'validate_map_story';
    }

    public function description(): string
    {
        return 'Check a map story without saving it: the stored story (`slug`) or a whole `document` you pass. '
            .'Returns `errors` (they would block a save) and `warnings` (plausibility: a unit jumping without an arrow, points far apart, ships on land, text lengths). '
            .'update_map_story already checks its patch; use this to look at a story before or after editing.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'slug' => $schema->string()->description('The story to check (or, with `document`, the story it would replace)'),
            'document' => $schema->object()->description('Optional: a whole map-story document to check instead of the stored one'),
        ];
    }

    public function handle(Request $request): Stringable|string
    {
        $document = $request['document'] ?? null;
        if (is_string($document)) {
            $document = MapStoryFile::decode($document);
        } elseif (is_array($document)) {
            $document = MapStoryFile::fromArray($document);
        }

        $story = null;
        if (trim((string) ($request['slug'] ?? '')) !== '') {
            try {
                $story = $this->findStory(['slug' => $request['slug']]);
            } catch (ToolArgumentException $e) {
                if ($document === null) {
                    return json_encode(['error' => $e->getMessage()], JSON_THROW_ON_ERROR);
                }
            }
        }
        if ($document === null && $story === null) {
            return json_encode(['error' => 'Give a `slug`, or a whole `document` to check.'], JSON_THROW_ON_ERROR);
        }
        if (! $document instanceof stdClass) {
            $document = $story instanceof MapStory ? $story->document : null;
        }
        if ($document === null) {
            return json_encode(['error' => '`document` must be a JSON object.'], JSON_THROW_ON_ERROR);
        }

        $result = ($this->check)($document, $story);

        return json_encode(['ok' => $result['errors'] === [], ...$result], MapStoryFile::JSON_FLAGS | JSON_THROW_ON_ERROR);
    }

    public function buildParts(array $args): array
    {
        throw new LogicException('ValidateMapStory is a read-only tool — it does not stage proposals.');
    }

    public function applyPart(array $payload, array $resolved): array
    {
        throw new LogicException('ValidateMapStory is a read-only tool — it does not apply parts.');
    }
}
