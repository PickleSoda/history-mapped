<?php

declare(strict_types=1);

namespace App\Services\Site;

use App\Actions\Chronicle\GetEntityChroniclesAction;
use App\Actions\Graph\GetEntityGraphAction;
use App\Enums\EntityType;
use App\Mcp\Support\EntityCards;
use App\Mcp\Support\RelationshipLabels;
use App\Mcp\Support\Text;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use Illuminate\Support\Str;

/**
 * Builds the pages the app renders for the public site: an entity, a
 * chronicle, and the not-found page. Each shows what the web app's page of
 * the same address shows, as plain text and links.
 */
class SitePages
{
    /** Longest meta description. Search engines cut near 160; other readers take more. */
    private const DESCRIPTION_CHARS = 300;

    private const ALIASES = 12;

    private const CHRONICLES = 12;

    public function __construct(
        private readonly GetEntityGraphAction $graph,
        private readonly GetEntityChroniclesAction $chronicles,
    ) {}

    /** The entity's page, or null when there is no such entity. */
    public function entity(string $id): ?SitePage
    {
        if (! Str::isUuid($id)) {
            return null;
        }

        // Named columns: the row also holds a 1536-number embedding.
        $entity = Entity::query()
            ->select([
                'entity_id', 'name', 'entity_type', 'entity_group', 'summary', 'significance',
                'description', 'wikidata_id', 'attributes', 'updated_at',
            ])
            ->with([
                'aliases',
                'primaryLocation' => fn ($q) => $q->select(['location_id', 'entity_id', 'location_name', 'is_primary', 'updated_at']),
            ])
            ->find(strtolower($id));

        if ($entity === null) {
            return null;
        }

        [$start, $end] = EntityCards::years([$entity->entity_id])[$entity->entity_id] ?? [null, null];
        $typeLabel = Text::typeLabel($entity->entity_type) ?? 'Entity';
        $span = SiteText::span($start, $end);
        $path = '/entities/'.$entity->entity_id;

        $aliases = $entity->aliases->pluck('name')
            ->map(fn ($name): string => trim((string) $name))
            ->filter(fn (string $name): bool => $name !== '' && $name !== $entity->name)
            ->unique()
            ->take(self::ALIASES)
            ->values()
            ->all();

        $description = Text::limit($entity->summary ?: ($entity->description ?: $entity->significance), self::DESCRIPTION_CHARS)
            ?? $entity->name.': '.lcfirst($typeLabel).($span !== null ? ', '.$span : '').', on '.SiteShell::SITE_NAME.'.';

        $body = view('site.entity', [
            'entity' => $entity,
            'typeLabel' => $typeLabel,
            'span' => $span,
            // A state's own place is often named after it: say it once.
            'place' => $this->place($entity),
            'aliases' => $aliases,
            'connections' => $this->connections($entity->entity_id),
            'chronicles' => ($this->chronicles)($entity->entity_id)->take(self::CHRONICLES),
        ])->render();

        return new SitePage(
            title: (string) $entity->name,
            description: $description,
            path: $path,
            body: $body,
            jsonLd: $this->webPage($entity->name, $description, $path, $entity->updated_at?->toAtomString(), array_filter([
                '@type' => match ($entity->entity_type) {
                    EntityType::Person => 'Person',
                    EntityType::City => 'City',
                    default => 'Thing',
                },
                'name' => $entity->name,
                'alternateName' => $aliases ?: null,
                'sameAs' => $entity->wikidata_id ? ['https://www.wikidata.org/wiki/'.$entity->wikidata_id] : null,
            ])),
            image: EntityCards::image($entity)['thumb_url'] ?? null,
        );
    }

    /** The chronicle's page, or null when there is none (archived ones are hidden). */
    public function chronicle(string $slug): ?SitePage
    {
        $chronicle = Chronicle::query()
            ->where('slug', $slug)
            ->notArchived()
            ->with([
                'entries' => fn ($q) => $q->select([
                    'entry_id', 'chronicle_id', 'sequence_order', 'start_year', 'end_year',
                    'primary_relationship_id', 'narrative_text',
                ]),
                'entries.primaryRelationship' => fn ($q) => $q->select([
                    'relationship_id', 'source_entity_id', 'target_entity_id',
                ]),
                'entries.primaryRelationship.sourceEntity' => fn ($q) => $q->select(['entity_id', 'name']),
                'entries.primaryRelationship.targetEntity' => fn ($q) => $q->select(['entity_id', 'name']),
                'entries.secondaryEntities' => fn ($q) => $q->select(['entities.entity_id', 'entities.name']),
            ])
            ->first();

        if ($chronicle === null) {
            return null;
        }

        $span = SiteText::span($chronicle->start_year, $chronicle->end_year);
        $path = '/chronicles/'.rawurlencode($chronicle->slug);

        $steps = $chronicle->entries->map(fn (ChronicleEntry $entry): array => [
            'span' => SiteText::span($entry->start_year, $entry->end_year),
            'paragraphs' => SiteText::paragraphs($entry->narrative_text),
            'entities' => collect([$entry->primaryRelationship?->sourceEntity, $entry->primaryRelationship?->targetEntity])
                ->concat($entry->secondaryEntities)
                ->filter()
                ->unique('entity_id')
                ->map(fn (Entity $e): array => ['id' => $e->entity_id, 'name' => $e->name])
                ->values()
                ->all(),
        ])->all();

        // The web app's own fallback line (ChronicleRoute.tsx).
        $description = Text::limit($chronicle->description, self::DESCRIPTION_CHARS)
            ?? sprintf(
                '%s: a chronicle in %d steps%s, on %s.',
                $chronicle->title,
                count($steps),
                $span !== null ? ', '.$span : '',
                SiteShell::SITE_NAME,
            );

        $body = view('site.chronicle', [
            'chronicle' => $chronicle,
            'span' => $span,
            'steps' => $steps,
        ])->render();

        return new SitePage(
            title: (string) $chronicle->title,
            description: $description,
            path: $path,
            body: $body,
            jsonLd: $this->webPage($chronicle->title, $description, $path, $chronicle->updated_at?->toAtomString()),
        );
    }

    /** What the web app shows at an address that has nothing: sent with a 404. */
    public function notFound(string $title, string $message): SitePage
    {
        return new SitePage(
            title: $title,
            description: $message,
            path: '/',
            body: view('site.not-found', ['title' => $title, 'message' => $message])->render(),
            index: false,
        );
    }

    private function place(Entity $entity): ?string
    {
        $place = trim((string) $entity->primaryLocation?->location_name);

        return $place === '' || mb_strtolower($place) === mb_strtolower((string) $entity->name) ? null : $place;
    }

    /**
     * The entity's connections in the graph's own order (most confident, then
     * the more important neighbour first), each as a phrase from this entity's
     * side: "ruled by", then the other entity.
     *
     * @return list<array{label: string, id: string, name: string, type: string|null, span: string|null}>
     */
    private function connections(string $entityId): array
    {
        $graph = ($this->graph)($entityId, ['depth' => 1, 'limit' => (int) config('site.connections')]);
        $nodes = collect($graph['nodes'])->keyBy('id');
        $rows = [];

        foreach ($graph['edges'] as $edge) {
            $outgoing = $edge['source'] === $entityId;
            $other = $nodes->get($outgoing ? $edge['target'] : $edge['source']);
            if ($other === null || $other['id'] === $entityId) {
                continue;
            }
            $rows[] = [
                'label' => RelationshipLabels::label($edge['relationship_type'], $outgoing),
                'id' => $other['id'],
                'name' => (string) $other['name'],
                'type' => Text::typeLabel($other['entity_type']),
                'span' => SiteText::span($other['start_year'], $other['end_year']),
            ];
        }

        return $rows;
    }

    /**
     * schema.org WebPage for a page of the site; `$about` describes its subject.
     *
     * @param  array<string, mixed>|null  $about
     * @return array<string, mixed>
     */
    private function webPage(string $name, string $description, string $path, ?string $modified, ?array $about = null): array
    {
        return array_filter([
            '@context' => 'https://schema.org',
            '@type' => 'WebPage',
            'name' => $name,
            'description' => $description,
            'url' => SiteShell::url($path),
            'dateModified' => $modified,
            'isPartOf' => ['@type' => 'WebSite', 'name' => SiteShell::SITE_NAME, 'url' => SiteShell::url('/')],
            'about' => $about,
        ]);
    }
}
