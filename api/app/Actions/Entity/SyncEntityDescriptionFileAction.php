<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Models\Entity;

/**
 * Set an entity's long description from a resources/entity-descriptions/*.md
 * file: front matter (`wikidata`, `name`) between `---` lines, then plain
 * paragraphs separated by blank lines (hard-wrapped lines are joined).
 *
 * The entity is found by Q-id (the most prominent row if several share it),
 * else by exact name when that name is unique. A description someone edited
 * since the last sync is left alone unless forced: the sync records the hash of
 * the text it wrote in `attributes._description_sync`.
 */
class SyncEntityDescriptionFileAction
{
    public const SYNC_KEY = '_description_sync';

    /**
     * @return array{status: 'set'|'unchanged'|'edited'|'unresolved'|'invalid', file: string, entity: string|null, message: string|null}
     */
    public function __invoke(string $path, bool $force = false): array
    {
        $file = basename($path);
        $parsed = self::parse((string) file_get_contents($path));
        if ($parsed === null || $parsed['body'] === '') {
            return ['status' => 'invalid', 'file' => $file, 'entity' => null, 'message' => 'needs front matter (wikidata/name) and a body'];
        }

        $entity = $this->resolve($parsed['meta']);
        if ($entity === null) {
            $ref = trim(($parsed['meta']['name'] ?? '').' '.($parsed['meta']['wikidata'] ?? ''));

            return ['status' => 'unresolved', 'file' => $file, 'entity' => null, 'message' => "no unique atlas entity for {$ref}"];
        }

        $body = $parsed['body'];
        $current = $entity->description;
        $attributes = is_array($entity->attributes) ? $entity->attributes : [];

        if ($current === $body) {
            return ['status' => 'unchanged', 'file' => $file, 'entity' => $entity->name, 'message' => null];
        }

        $untouched = $current === null || trim($current) === '' || sha1($current) === ($attributes[self::SYNC_KEY] ?? null);
        if (! $untouched && ! $force) {
            return ['status' => 'edited', 'file' => $file, 'entity' => $entity->name, 'message' => 'edited since the last sync; --force overwrites'];
        }

        $entity->forceFill([
            'description' => $body,
            'attributes' => [...$attributes, self::SYNC_KEY => sha1($body)],
        ])->save();

        return ['status' => 'set', 'file' => $file, 'entity' => $entity->name, 'message' => null];
    }

    /**
     * @return array{meta: array<string, string>, body: string}|null
     */
    public static function parse(string $text): ?array
    {
        $text = str_replace(["\r\n", "\r"], "\n", $text);
        if (! preg_match('/\A---\n(.*?)\n---\n?(.*)\z/s', $text, $m)) {
            return null;
        }

        $meta = [];
        foreach (explode("\n", $m[1]) as $line) {
            if (preg_match('/^\s*([A-Za-z_]+)\s*:\s*(.*?)\s*$/', $line, $kv)) {
                $meta[strtolower($kv[1])] = trim($kv[2], " \t\"'");
            }
        }

        $paragraphs = preg_split('/\n\s*\n/', trim($m[2])) ?: [];
        $paragraphs = array_values(array_filter(array_map(
            fn (string $p) => trim((string) preg_replace('/\s*\n\s*/', ' ', $p)),
            $paragraphs,
        ), fn (string $p) => $p !== ''));

        return ['meta' => $meta, 'body' => implode("\n\n", $paragraphs)];
    }

    /** @param  array<string, string>  $meta */
    private function resolve(array $meta): ?Entity
    {
        $qid = $meta['wikidata'] ?? '';
        if (preg_match('/^Q[1-9][0-9]*$/', $qid)) {
            $byQid = Entity::query()
                ->where('wikidata_id', $qid)
                ->orderByRaw('impact_score DESC NULLS LAST')
                ->orderBy('entity_id')
                ->first();
            if ($byQid !== null) {
                return $byQid;
            }
        }

        $name = $meta['name'] ?? '';
        if ($name === '') {
            return null;
        }
        $byName = Entity::query()->where('name', $name)->limit(2)->get();

        return $byName->count() === 1 ? $byName->first() : null;
    }
}
