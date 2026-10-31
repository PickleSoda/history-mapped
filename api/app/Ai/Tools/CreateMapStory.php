<?php

declare(strict_types=1);

namespace App\Ai\Tools;

use App\Actions\MapStory\CheckMapStoryAction;
use App\Actions\MapStory\CreateMapStoryAction;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\MapStory;
use App\Services\EntityReferenceResolver;
use App\Support\MapStory\MapStoryVocabulary as V;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Symfony\Component\HttpKernel\Exception\UnprocessableEntityHttpException;

/**
 * Propose a new map story for an entity (or a chronicle's map layer): a
 * schema-3 skeleton with the kind, title, year and optional sides and units
 * (CreateMapStoryAction). Fill it in afterwards with update_map_story.
 */
class CreateMapStory extends AgentTool
{
    public function __construct(private CreateMapStoryAction $create, private CheckMapStoryAction $check) {}

    public static function name(): string
    {
        return 'create_map_story';
    }

    public function description(): string
    {
        return 'Propose a new map story (a battle map, an epidemic, a trade network…) for an entity, or the map layer of a chronicle. '
            .'It starts as a valid skeleton: placeholder intro/outcome, one step, the sides and units you give (a battle gets two sides by default), '
            .'placed at the entity\'s map point. After the operator applies it, fill it in with update_map_story (get_map_story shows the paths).';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'entity_id' => $schema->string()->description('UUID of the entity the story belongs to (e.g. the battle)'),
            'chronicle_id' => $schema->string()->description('Or: UUID of the chronicle whose map layer this is'),
            'kind' => $schema->string()->enum(V::STORY_KINDS)->description('battle, naval_battle, siege, campaign, war, trade_route, epidemic, migration, exploration, expansion, diffusion or event')->required(),
            'title' => $schema->string()->description('Story title, e.g. "Battle of Cannae"')->required(),
            'year' => $schema->integer()->description('The first year; BCE negative (216 BC = -216)')->required(),
            'sides' => $schema->array()->items($schema->object(fn (JsonSchema $s) => [
                'id' => $s->string()->description('lowercase-kebab id')->required(),
                'name' => $s->string()->required(),
                'color' => $s->string()->description('#rrggbb'),
            ]))->description('Optional: the sides (battles need two)'),
            'units' => $schema->array()->items($schema->object(fn (JsonSchema $s) => [
                'id' => $s->string()->description('lowercase-kebab id')->required(),
                'side' => $s->string()->description('a side id (omit when there are no sides)'),
                'kind' => $s->string()->enum(V::UNIT_KINDS)->required(),
                'label' => $s->string()->description('≤ 28 characters, drawn on the map')->required(),
            ]))->description('Optional: the bodies of troops, ships or groups'),
        ];
    }

    public function buildParts(array $args): array
    {
        $owner = $this->owner($args);
        $kind = (string) ($args['kind'] ?? '');
        if (! in_array($kind, V::STORY_KINDS, true)) {
            throw new ToolArgumentException('kind: one of '.implode(', ', V::STORY_KINDS));
        }
        $title = trim((string) ($args['title'] ?? ''));
        if ($title === '' || ! is_numeric($args['year'] ?? null)) {
            throw new ToolArgumentException('Give a `title` and the first `year` (BCE negative).');
        }
        $sides = is_array($args['sides'] ?? null) && $args['sides'] !== [] ? array_values($args['sides']) : null;
        $units = is_array($args['units'] ?? null) && $args['units'] !== [] ? array_values($args['units']) : null;

        $skeleton = $this->create->skeleton($owner, $kind, $title, (int) $args['year'], $sides, $units);
        $check = ($this->check)($skeleton);
        if ($check['errors'] !== []) {
            throw new ToolArgumentException("That story would not be valid — nothing staged:\n- ".implode("\n- ", array_slice($check['errors'], 0, 20)));
        }

        $ownerName = $owner instanceof Entity ? $owner->name : $owner->title;

        return [[
            'key' => 'map_story',
            'tool' => self::name(),
            'payload' => [
                'owner' => $owner instanceof Entity ? 'entity' : 'chronicle',
                'owner_id' => $owner instanceof Entity ? $owner->entity_id : $owner->chronicle_id,
                'kind' => $kind, 'title' => $title, 'year' => (int) $args['year'],
                'sides' => $sides, 'units' => $units, 'slug' => $skeleton->slug,
            ],
            'human_diff' => [
                'summary' => "Create map story '{$title}' ({$kind}, {$args['year']}) for {$ownerName}",
                'diff' => [
                    'slug' => ['from' => null, 'to' => $skeleton->slug],
                    'sides' => ['from' => null, 'to' => array_column($skeleton->sides, 'name')],
                    'units' => ['from' => null, 'to' => array_column($skeleton->units, 'label')],
                ],
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $owner = $payload['owner'] === 'entity'
            ? Entity::query()->findOrFail($payload['owner_id'])
            : Chronicle::query()->findOrFail($payload['owner_id']);
        $slug = MapStory::query()->where('slug', $payload['slug'])->exists() ? null : $payload['slug'];
        $userId = is_numeric($resolved['user_id'] ?? null) ? (int) $resolved['user_id'] : null;

        $result = ($this->create)($owner, $payload['kind'], $payload['title'], (int) $payload['year'], $payload['sides'] ?? null, $payload['units'] ?? null, 'ai', $userId, $slug);
        if ($result['errors'] !== [] || $result['story'] === null) {
            throw new UnprocessableEntityHttpException('Could not create the story: '.implode(' · ', array_slice($result['errors'], 0, 5)));
        }

        return ['result_id' => $result['story']->story_id, 'summary' => "Created map story {$result['story']->slug}"];
    }

    private function owner(array $args): Entity|Chronicle
    {
        $entity = trim((string) ($args['entity_id'] ?? ''));
        if ($entity !== '') {
            return (EntityReferenceResolver::isUuid($entity) ? Entity::query()->find(strtolower($entity)) : null)
                ?? throw new ToolArgumentException("No entity '{$entity}'. Pass the entity's UUID (get_entity_context resolves a name).");
        }
        $chronicle = trim((string) ($args['chronicle_id'] ?? ''));
        if ($chronicle !== '') {
            return (EntityReferenceResolver::isUuid($chronicle) ? Chronicle::query()->find(strtolower($chronicle)) : null)
                ?? throw new ToolArgumentException("No chronicle '{$chronicle}'.");
        }
        throw new ToolArgumentException('Give the `entity_id` the story belongs to (or a `chronicle_id`).');
    }
}
