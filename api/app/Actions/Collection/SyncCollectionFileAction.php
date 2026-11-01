<?php

declare(strict_types=1);

namespace App\Actions\Collection;

use App\Enums\CollectionStatus;
use App\Models\Collection;
use App\Models\Entity;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Validator as ValidatorInstance;

/**
 * Load one resources/collections/<slug>.json file into `collections`,
 * upserting by slug. The file is the source of truth (there is no admin
 * editing), so a changed file overwrites its row. Items are stored as
 * written and resolved when served; only `cover_qid` is resolved here, to
 * `cover_entity_id` (a cover that matches no entity is a warning, not an
 * error). File format: docs/schemas/collections.md.
 */
class SyncCollectionFileAction
{
    /**
     * @return array{status: 'created'|'updated'|'unchanged'|'invalid', slug: string, errors: list<string>, warnings: list<string>}
     */
    public function __invoke(string $path): array
    {
        $name = basename($path, '.json');
        $data = json_decode((string) file_get_contents($path), true);
        if (! is_array($data) || array_is_list($data)) {
            return $this->result('invalid', $name, ['not a JSON object'.(json_last_error() !== JSON_ERROR_NONE ? ': '.json_last_error_msg() : '')]);
        }

        $errors = $this->validate($data, $name);
        if ($errors !== []) {
            return $this->result('invalid', $name, $errors);
        }

        $warnings = [];
        $cover = null;
        if (! empty($data['cover_qid'])) {
            $cover = self::entityId($data['cover_qid']);
            if ($cover === null) {
                $warnings[] = "cover_qid {$data['cover_qid']}: no such entity, so no cover";
            }
        }

        $row = Collection::query()->firstOrNew(['slug' => $name]);
        $before = $row->exists ? self::snapshot($row) : null;
        $row->fill([
            'title' => $data['title'],
            'subtitle' => $data['subtitle'] ?? null,
            'description' => $data['description'] ?? null,
            'cover_entity_id' => $cover,
            'items' => self::items($data['items']),
            'status' => $data['status'] ?? CollectionStatus::Published->value,
            'sort_order' => $data['sort_order'] ?? 0,
        ]);

        if ($before !== null && $before == self::snapshot($row)) {
            return $this->result('unchanged', $name, warnings: $warnings);
        }

        $status = $row->exists ? 'updated' : 'created';
        $row->save();

        return $this->result($status, $name, warnings: $warnings);
    }

    /**
     * @param  array<string, mixed>  $data
     * @return list<string>
     */
    private function validate(array $data, string $name): array
    {
        $validator = Validator::make($data, [
            'slug' => ['required', 'string', 'max:120', 'regex:'.Collection::SLUG_PATTERN],
            'title' => ['required', 'string', 'max:255'],
            'subtitle' => ['nullable', 'string', 'max:255'],
            'description' => ['nullable', 'string', 'max:10000'],
            'cover_qid' => ['nullable', 'string', 'max:64'],
            'status' => ['sometimes', 'string', Rule::enum(CollectionStatus::class)],
            'sort_order' => ['sometimes', 'integer'],
            'items' => ['present', 'array', 'list', 'max:200'],
            'items.*' => ['array:kind,ref,note'],
            'items.*.kind' => ['required', 'string', Rule::in(Collection::KINDS)],
            'items.*.ref' => ['required', 'string', 'max:255'],
            'items.*.note' => ['nullable', 'string', 'max:1000'],
        ]);

        $validator->after(function (ValidatorInstance $v) use ($data, $name): void {
            foreach (array_keys($data) as $key) {
                if (! str_starts_with((string) $key, '_') && ! in_array($key, ['slug', 'title', 'subtitle', 'description', 'cover_qid', 'status', 'sort_order', 'items'], true)) {
                    $v->errors()->add($key, "unknown field '{$key}'");
                }
            }
            if (is_string($data['slug'] ?? null) && $data['slug'] !== $name) {
                $v->errors()->add('slug', "slug '{$data['slug']}' must match the file name '{$name}'");
            }
            if (is_string($data['cover_qid'] ?? null) && $data['cover_qid'] !== '' && ! Collection::isEntityRef($data['cover_qid'])) {
                $v->errors()->add('cover_qid', "cover_qid '{$data['cover_qid']}' is neither a Wikidata id (Q123) nor an entity uuid");
            }

            $seen = [];
            foreach (is_array($data['items'] ?? null) ? $data['items'] : [] as $i => $item) {
                $kind = is_array($item) ? ($item['kind'] ?? null) : null;
                $ref = is_array($item) ? ($item['ref'] ?? null) : null;
                if (! is_string($kind) || ! is_string($ref)) {
                    continue;
                }
                if ($kind === 'entity' && ! Collection::isEntityRef($ref)) {
                    $v->errors()->add("items.{$i}.ref", "items.{$i}: an entity ref is a Wikidata id (Q123) or an entity uuid, not '{$ref}'");
                } elseif ($kind !== 'entity' && preg_match(Collection::REF_PATTERN, $ref) !== 1) {
                    $v->errors()->add("items.{$i}.ref", "items.{$i}: a {$kind} ref is a slug, not '{$ref}'");
                }
                $key = $kind.':'.Str::lower($ref);
                if (isset($seen[$key])) {
                    $v->errors()->add("items.{$i}", "items.{$i}: {$kind} '{$ref}' is already item {$seen[$key]}");
                }
                $seen[$key] ??= $i;
            }
        });

        return array_values($validator->errors()->all());
    }

    /**
     * Items in a fixed shape (no empty notes; uuids lower-case).
     *
     * @param  list<array{kind: string, ref: string, note?: string|null}>  $items
     * @return list<array{kind: string, ref: string, note?: string}>
     */
    private static function items(array $items): array
    {
        return array_map(function (array $item): array {
            $ref = Str::isUuid($item['ref']) ? Str::lower($item['ref']) : $item['ref'];
            $note = trim((string) ($item['note'] ?? ''));

            return ['kind' => $item['kind'], 'ref' => $ref, ...($note === '' ? [] : ['note' => $note])];
        }, $items);
    }

    /** The entity a Wikidata id (the most prominent one, should two share it) or a uuid names. */
    private static function entityId(string $ref): ?string
    {
        $query = Entity::query();
        $query = Str::isUuid($ref)
            ? $query->whereKey(Str::lower($ref))
            : $query->where('wikidata_id', $ref)->orderByRaw('impact_score DESC NULLS LAST');

        $id = $query->value('entity_id');

        return is_string($id) ? $id : null;
    }

    /**
     * The synced fields, to tell an unchanged file from a changed one (`==`:
     * jsonb does not keep an item's key order).
     *
     * @return array<string, mixed>
     */
    private static function snapshot(Collection $row): array
    {
        return [
            'title' => $row->title,
            'subtitle' => $row->subtitle,
            'description' => $row->description,
            'cover_entity_id' => $row->cover_entity_id,
            'items' => $row->items,
            'status' => $row->status?->value,
            'sort_order' => $row->sort_order,
        ];
    }

    /**
     * @param  'created'|'updated'|'unchanged'|'invalid'  $status
     * @param  list<string>  $errors
     * @param  list<string>  $warnings
     * @return array{status: 'created'|'updated'|'unchanged'|'invalid', slug: string, errors: list<string>, warnings: list<string>}
     */
    private function result(string $status, string $slug, array $errors = [], array $warnings = []): array
    {
        return ['status' => $status, 'slug' => $slug, 'errors' => $errors, 'warnings' => $warnings];
    }
}
