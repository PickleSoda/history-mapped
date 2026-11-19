<?php

declare(strict_types=1);

namespace App\Mcp\Tools;

use App\Mcp\Resources\TimelineApp;
use App\Mcp\Support\AtlasUrl;
use App\Mcp\Support\ChronicleHeadings;
use App\Mcp\Support\Reply;
use App\Mcp\Support\Text;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Mcp\Request;
use Laravel\Mcp\Response;
use Laravel\Mcp\ResponseFactory;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Attributes\RendersApp;
use Laravel\Mcp\Server\Tool;
use Laravel\Mcp\Server\Tools\Annotations\IsIdempotent;
use Laravel\Mcp\Server\Tools\Annotations\IsReadOnly;

#[Description('Read one chronicle, a curated narrative told as dated steps in order, each tied to an entity and a place where known. Use the slug from find_chronicles, search_atlas or get_entity. Long chronicles are cut to their first 60 steps; the text says so.')]
#[RendersApp(resource: TimelineApp::class)]
#[IsReadOnly]
#[IsIdempotent]
class GetChronicle extends Tool
{
    private const ENTRIES = 60;

    private const ENTRY_CHARS = 600;

    public function schema(JsonSchema $schema): array
    {
        return [
            'slug' => $schema->string()->description('Chronicle slug.')->min(1)->max(255)->required(),
        ];
    }

    public function outputSchema(JsonSchema $schema): array
    {
        return [
            'chronicle' => $schema->object([
                'slug' => $schema->string()->required(),
                'title' => $schema->string()->required(),
                'summary' => $schema->string()->nullable()->required(),
                'start_year' => $schema->integer()->nullable()->required(),
                'end_year' => $schema->integer()->nullable()->required(),
                'tags' => $schema->array()->items($schema->string())->required(),
                'atlas_url' => $schema->string()->required(),
            ])->required(),
            'entries' => $schema->array()->items($schema->object([
                'sequence' => $schema->integer()->required(),
                'title' => $schema->string()->description('Short heading: the name of the entity the step is about, else its first clause. The text does not start with it again in the view.')->required(),
                'start_year' => $schema->integer()->nullable()->required(),
                'end_year' => $schema->integer()->nullable()->required(),
                'date_label' => $schema->string()->nullable()->required(),
                'text' => $schema->string()->description('The step, at most 600 characters.')->required(),
                'entity' => $schema->object([
                    'id' => $schema->string()->required(),
                    'name' => $schema->string()->required(),
                    'type' => $schema->string()->required(),
                    'atlas_url' => $schema->string()->required(),
                ])->nullable()->required(),
                'lng' => $schema->number()->nullable()->required(),
                'lat' => $schema->number()->nullable()->required(),
            ]))->description('At most 60 steps, in order.')->required(),
        ];
    }

    public function handle(Request $request): Response|ResponseFactory
    {
        $input = $request->validate(['slug' => ['required', 'string', 'max:255']]);

        $chronicle = Chronicle::query()->with('tags')->where('slug', $input['slug'])->notArchived()->first();
        if ($chronicle === null) {
            return Response::error("No chronicle has the slug \"{$input['slug']}\". Use find_chronicles to list them.");
        }

        $total = $chronicle->entries()->count();
        $entries = $chronicle->entries()
            ->with(['secondaryEntities', 'primaryRelationship.sourceEntity', 'primaryRelationship.targetEntity'])
            ->limit(self::ENTRIES)
            ->get();

        $headings = ChronicleHeadings::forEntries($entries->map(fn (ChronicleEntry $e): array => [
            'text' => (string) $e->narrative_text,
            'entities' => $this->linked($e),
        ])->values()->all());
        $rows = $entries->values()->map(fn (ChronicleEntry $e, int $i): array => $this->entry($e, $headings[$i]))->all();

        $head = [
            'slug' => $chronicle->slug,
            'title' => $chronicle->title,
            'summary' => Text::limit($chronicle->description, 1000),
            'start_year' => $chronicle->start_year,
            'end_year' => $chronicle->end_year,
            'tags' => $chronicle->tags->pluck('slug')->values()->all(),
            'atlas_url' => AtlasUrl::chronicle($chronicle->slug),
        ];

        $dates = Text::dateLabel($chronicle->start_year, $chronicle->end_year);
        $text = sprintf(
            'Chronicle "%s"%s: %s%s',
            $chronicle->title,
            $dates ? " ({$dates})" : '',
            $total > self::ENTRIES
                ? 'capped at the first '.self::ENTRIES." of {$total} steps."
                : count($rows).' step(s).',
            $head['summary'] ? ' '.$head['summary'] : '',
        );

        return Reply::make($text, ['chronicle' => $head, 'entries' => $rows]);
    }

    /**
     * The entities a step is about: the primary relationship's two ends and
     * the linked entities, for ChronicleHeadings.
     *
     * @return list<array{name: string, event: bool, primary: bool, impact: int|null}>
     */
    private function linked(ChronicleEntry $e): array
    {
        $r = $e->primaryRelationship;
        $primary = array_values(array_filter([$r?->sourceEntity, $r?->targetEntity]));
        $out = [];
        foreach ([...$primary, ...$e->secondaryEntities->all()] as $i => $x) {
            $out[] = [
                'name' => (string) $x->name,
                'event' => str_starts_with((string) $x->entity_type?->value, 'event_'),
                'primary' => $i < count($primary),
                'impact' => $x->impact_score !== null ? (int) $x->impact_score : null,
            ];
        }

        return $out;
    }

    /** @return array<string, mixed> */
    private function entry(ChronicleEntry $e, string $heading): array
    {
        $subject = $e->secondaryEntities->first();
        $location = is_array($e->approximate_location) ? $e->approximate_location : [];
        $lng = $location['lng'] ?? $location['lon'] ?? null;
        $lat = $location['lat'] ?? null;

        return [
            'sequence' => (int) $e->sequence_order,
            'title' => $heading,
            'start_year' => $e->start_year,
            'end_year' => $e->end_year,
            'date_label' => Text::dateLabel($e->start_year, $e->end_year),
            'text' => (string) Text::limit($e->narrative_text, self::ENTRY_CHARS),
            'entity' => $subject instanceof Entity ? [
                'id' => $subject->entity_id,
                'name' => $subject->name,
                'type' => $subject->entity_type?->value,
                'atlas_url' => AtlasUrl::entity($subject->entity_id),
            ] : null,
            'lng' => is_numeric($lng) ? round((float) $lng, 5) : null,
            'lat' => is_numeric($lat) ? round((float) $lat, 5) : null,
        ];
    }
}
