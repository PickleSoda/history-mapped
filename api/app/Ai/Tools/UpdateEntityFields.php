<?php

namespace App\Ai\Tools;

use App\Actions\Entity\ApplyEntityEditsAction;
use App\Actions\Entity\BackfillEntityAction;
use App\DTOs\EntityData;
use App\Enums\ConfidenceLevel;
use App\Enums\DateResolutionMethod;
use App\Enums\DurationType;
use App\Enums\EntityType;
use App\Enums\IconClass;
use App\Enums\LocationResolutionMethod;
use App\Enums\VerificationStatus;
use App\Http\Requests\Admin\UpdateEntityRequest;
use App\Models\Entity;
use App\Models\User;
use App\Support\EntityAttributeCatalog;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\Validator;
use Symfony\Component\HttpKernel\Exception\AccessDeniedHttpException;

/**
 * Edit any field the admin entity form edits, through the same validation and
 * the same write path (ApplyEntityEditsAction). Fields the model doesn't send
 * are untouched; `clear` empties a field; tags and alternative names are
 * added/removed item by item; type-specific `attributes` are checked against
 * EntityAttributeCatalog. Geometry moves through set_entity_location.
 */
class UpdateEntityFields extends AgentTool
{
    /** Plain fields: tool argument = UpdateEntityRequest key. */
    private const SCALAR_FIELDS = [
        'name', 'summary', 'significance', 'description', 'entity_type', 'date_raw', 'date_method', 'date_confidence',
        'duration_type', 'location_name', 'location_confidence', 'location_method', 'impact_score',
        'display_priority', 'confidence', 'confidence_notes', 'icon_class', 'entity_color', 'verification_status',
    ];

    /** What `clear` may empty (start_year / end_year make that bound open). */
    private const CLEARABLE = [
        'summary', 'significance', 'description', 'start_year', 'end_year', 'date_raw', 'date_method', 'date_confidence',
        'duration_type', 'location_name', 'location_confidence', 'location_method', 'impact_score',
        'display_priority', 'confidence', 'confidence_notes', 'icon_class', 'entity_color',
    ];

    public function __construct(
        private ApplyEntityEditsAction $apply,
        private BackfillEntityAction $backfill,
    ) {}

    public static function name(): string
    {
        return 'update_entity_fields';
    }

    public function description(): string
    {
        return 'Change fields on an existing entity — anything the admin edit form can change: name, summary, significance, long description, type, dates and how they were resolved, '
            .'location name/confidence, impact score, display priority, confidence, icon, color, verification status, tags, alternative names, and the '
            .'type-specific attributes listed in get_entity_context → attribute_fields. Send only what changes; everything else is kept. '
            .'To empty a field put its name in `clear`. To move the map point use set_entity_location instead.';
    }

    public function schema(JsonSchema $schema): array
    {
        $text = fn (string $about) => $schema->string()->description($about);
        $list = fn (string $about) => $schema->array()->items($schema->string())->description($about);

        return [
            'entity_id' => $schema->string()->description('UUID of the entity to update')->required(),
            'name' => $text('New canonical name'),
            'summary' => $text('Short neutral description (1–3 sentences)'),
            'significance' => $text('Why it matters historically'),
            'description' => $text('Long-form account: 3–6 plain paragraphs separated by a blank line (background, what happened, consequences). Not the one-sentence summary; no markdown'),
            'entity_type' => $schema->string()->enum(EntityType::class)->description('New entity type; the group follows from it'),
            'start_year' => $schema->integer()->description('Start year. BCE is negative: 44 BCE = -44'),
            'end_year' => $schema->integer()->description('End year. BCE is negative'),
            'start_date' => $text("Exact start when known, instead of start_year: 'YYYY-MM' or 'YYYY-MM-DD', BCE with a leading minus ('-0044-03-15')"),
            'end_date' => $text('Exact end when known, instead of end_year; same format as start_date'),
            'date_raw' => $text('The date as the source writes it, e.g. "c. 1200 BCE" or "reigned 117–138"'),
            'date_method' => $schema->string()->enum(DateResolutionMethod::class)->description('How the dates were resolved; human_assigned when taken from the operator or a cited source'),
            'date_confidence' => $schema->string()->enum(ConfidenceLevel::class)->description('Confidence in the dates'),
            'duration_type' => $schema->string()->enum(DurationType::class)->description('point = a moment (battle), period = has an end, ongoing = still exists, uncertain'),
            'location_name' => $text('Name of the place the point marks, e.g. "Shore near Ostia"'),
            'location_confidence' => $schema->string()->enum(ConfidenceLevel::class)->description('Confidence in the map point'),
            'location_method' => $schema->string()->enum(LocationResolutionMethod::class)->description('How the point was found'),
            'impact_score' => $schema->number()->description('Historical prominence 0–100 (drives map visibility; 80+ shows at world zoom)'),
            'display_priority' => $schema->integer()->description('Map drawing priority 0–100; higher draws first'),
            'confidence' => $schema->string()->enum(ConfidenceLevel::class)->description('Overall confidence in the record'),
            'confidence_notes' => $text('Why the confidence is what it is; open questions'),
            'icon_class' => $schema->string()->enum(IconClass::class)->description('Map icon'),
            'entity_color' => $text('Map color as #rrggbb'),
            'verification_status' => $schema->string()->enum(VerificationStatus::class)->description('Review status. Applying a change needs the operator to hold the verify permission'),
            'attributes' => $schema->object()->description('Type-specific fields as {"key": value}. Only keys from get_entity_context → attribute_fields for this entity\'s type; use their allowed values exactly. Put a key in `clear` to empty it.'),
            'add_tags' => $list('Tags to add (short lowercase phrases)'),
            'remove_tags' => $list('Tags to remove'),
            'add_alternative_names' => $list('Alternative names / spellings to add'),
            'remove_alternative_names' => $list('Alternative names to remove'),
            'clear' => $list('Fields to empty: '.implode(', ', self::CLEARABLE).', or an attribute key'),
        ];
    }

    public function buildParts(array $args): array
    {
        $e = Entity::with(['primaryTemporalRange', 'primaryLocation', 'entityTags', 'aliases'])->findOrFail($args['entity_id']);
        $type = $args['entity_type'] ?? $e->entity_type->value;

        [$changes, $tags, $aliases] = $this->changesFrom($args, $type);
        $this->validate($changes, $type);

        $diff = $this->diff($e, $changes, $tags, $aliases);
        if ($diff === []) {
            throw new ToolArgumentException('Nothing to change: send at least one field (or `clear` / add_ / remove_ lists) that differs from the current value.');
        }

        return [[
            'key' => 'fields',
            'tool' => self::name(),
            'payload' => [
                'entity_id' => $e->entity_id,
                'changes' => $changes,
                'tags' => $tags,
                'alternative_names' => $aliases,
            ],
            'human_diff' => [
                'summary' => "Update fields on {$e->name}: ".implode(', ', array_keys($diff)),
                'diff' => $diff,
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $e = Entity::findOrFail($payload['entity_id']);
        $changes = $payload['changes'] ?? self::legacyChanges($payload);

        if (array_key_exists('verification_status', $changes)
            && $changes['verification_status'] !== $e->verification_status?->value
            && ! User::find($resolved['user_id'] ?? null)?->can('entities.verify')) {
            throw new AccessDeniedHttpException('Changing the verification status needs the entities.verify permission.');
        }

        $e = ($this->apply)($e, $changes, $payload['tags'] ?? [], $payload['alternative_names'] ?? []);

        if (array_intersect(array_keys($changes), ['temporal_start', 'temporal_end']) !== []) {
            ($this->backfill)($e);
        }

        return ['result_id' => $e->entity_id, 'summary' => 'Fields updated'];
    }

    /**
     * Tool arguments → UpdateEntityRequest-keyed changes plus the tag and alias edits.
     *
     * @return array{0: array<string, mixed>, 1: array{add: list<string>, remove: list<string>}, 2: array{add: list<string>, remove: list<string>}}
     */
    private function changesFrom(array $args, string $type): array
    {
        $changes = Arr::only($args, self::SCALAR_FIELDS);

        foreach (['start' => 'temporal_start', 'end' => 'temporal_end'] as $bound => $key) {
            if (isset($args["{$bound}_date"]) && $args["{$bound}_date"] !== '') {
                $changes[$key] = (string) $args["{$bound}_date"];
            } elseif (isset($args["{$bound}_year"])) {
                $changes[$key] = (string) $args["{$bound}_year"];
            }
        }

        $attributes = is_array($args['attributes'] ?? null) ? $args['attributes'] : [];
        $catalog = EntityAttributeCatalog::fieldsFor($type);

        foreach ((array) ($args['clear'] ?? []) as $field) {
            match (true) {
                $field === 'start_year' => $changes['temporal_start'] = null,
                $field === 'end_year' => $changes['temporal_end'] = null,
                in_array($field, self::CLEARABLE, true) => $changes[$field] = null,
                isset($catalog[$field]) => $attributes[$field] = null,
                default => throw new ToolArgumentException("Cannot clear '{$field}'. Clearable: ".implode(', ', self::CLEARABLE).', or an attribute key of this type.'),
            };
        }

        if (array_key_exists('temporal_start', $changes) && array_key_exists('temporal_end', $changes)
            && $changes['temporal_start'] === null && $changes['temporal_end'] === null) {
            throw new ToolArgumentException('Keep at least one of start_year / end_year; clear only the bound that is unknown.');
        }

        foreach ($attributes as $key => $value) {
            if ($problem = EntityAttributeCatalog::problem($type, (string) $key, $value)) {
                throw new ToolArgumentException($problem.'. See get_entity_context → attribute_fields.');
            }
        }
        if ($attributes !== []) {
            $changes['attributes'] = $attributes;
        }

        $edit = fn (string $add, string $remove) => [
            'add' => array_values(array_filter(array_map('trim', (array) ($args[$add] ?? [])))),
            'remove' => array_values(array_filter(array_map('trim', (array) ($args[$remove] ?? [])))),
        ];

        return [$changes, $edit('add_tags', 'remove_tags'), $edit('add_alternative_names', 'remove_alternative_names')];
    }

    /** Check the changes with the admin form's own rules for this entity type. */
    private function validate(array $changes, string $type): void
    {
        $rules = UpdateEntityRequest::create('/', 'PUT', ['entity_type' => $type])->rules();
        $validator = Validator::make($changes, Arr::only($rules, array_merge(
            array_keys($changes),
            array_map(fn ($key) => "attributes.{$key}", array_keys($changes['attributes'] ?? [])),
        )));

        if ($validator->fails()) {
            throw new ToolArgumentException('Invalid value: '.implode(' ', $validator->errors()->all()));
        }
    }

    /**
     * Field-level from → to for the proposal card; unchanged fields left out.
     *
     * @return array<string, array{from: mixed, to: mixed}>
     */
    private function diff(Entity $e, array $changes, array $tags, array $aliases): array
    {
        $stored = is_array($e->attributes) ? $e->attributes : [];
        $current = ApplyEntityEditsAction::currentValues($e) + Arr::only($stored, EntityData::MOVED_KEYS);
        $diff = [];

        foreach (Arr::except($changes, ['attributes']) as $field => $to) {
            $from = $current[$field] ?? null;
            if ((string) $from !== (string) $to || ($from === null) !== ($to === null)) {
                $label = ['temporal_start' => 'start', 'temporal_end' => 'end'][$field] ?? $field;
                $diff[$label] = ['from' => $from, 'to' => $to];
            }
        }

        foreach ($changes['attributes'] ?? [] as $key => $to) {
            $from = $stored[$key] ?? null;
            if ($from !== $to) {
                $diff["attributes.{$key}"] = ['from' => $from, 'to' => $to];
            }
        }

        $tagNow = ApplyEntityEditsAction::manualTags($e);
        $tagNext = ApplyEntityEditsAction::applyListEdit($tagNow, $tags);
        if ($tagNext !== $tagNow) {
            $diff['tags'] = ['from' => $tagNow, 'to' => $tagNext];
        }

        $aliasNow = $e->aliases->pluck('name')->values()->all();
        $aliasNext = ApplyEntityEditsAction::applyListEdit($aliasNow, $aliases);
        if ($aliasNext !== $aliasNow) {
            $diff['alternative_names'] = ['from' => $aliasNow, 'to' => $aliasNext];
        }

        return $diff;
    }

    /**
     * Proposals staged before `changes` existed carried the fields at the top
     * level (start_year / end_year as integers).
     *
     * @return array<string, mixed>
     */
    private static function legacyChanges(array $payload): array
    {
        $changes = Arr::only($payload, ['name', 'summary', 'significance', 'entity_type']);
        foreach (['start_year' => 'temporal_start', 'end_year' => 'temporal_end'] as $old => $key) {
            if (isset($payload[$old])) {
                $changes[$key] = (string) $payload[$old];
            }
        }

        return $changes;
    }
}
