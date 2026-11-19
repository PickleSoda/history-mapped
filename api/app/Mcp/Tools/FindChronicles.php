<?php

declare(strict_types=1);

namespace App\Mcp\Tools;

use App\Actions\Chronicle\ListChroniclesAction;
use App\Mcp\Support\AtlasUrl;
use App\Mcp\Support\EntityCards;
use App\Mcp\Support\Reply;
use App\Mcp\Support\Text;
use App\Models\Chronicle;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Mcp\Request;
use Laravel\Mcp\ResponseFactory;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Tool;
use Laravel\Mcp\Server\Tools\Annotations\IsIdempotent;
use Laravel\Mcp\Server\Tools\Annotations\IsReadOnly;

#[Description('Find chronicles: the atlas\'s curated, step-by-step narratives of a period, war, dynasty or theme (for example "The Human Story" chapters or a campaign). Search by words in the title or tag names, and/or filter by tag slugs (an era such as "medieval", a region such as "europe", a theme). Give a query, tags, or both. Open one with get_chronicle.')]
#[IsReadOnly]
#[IsIdempotent]
class FindChronicles extends Tool
{
    public function schema(JsonSchema $schema): array
    {
        return [
            'query' => $schema->string()->description('Words from a chronicle title, slug or tag name.')->min(2)->max(200),
            'tags' => $schema->array()->items($schema->string())
                ->description('Tag slugs; one tag from each facet (era, region, theme, type) must match.'),
            'limit' => $schema->integer()->description('Chronicles to return, 1 to 20 (default 10).')->min(1)->max(20),
        ];
    }

    public function outputSchema(JsonSchema $schema): array
    {
        return [
            'chronicles' => $schema->array()->items($schema->object([
                'slug' => $schema->string()->required(),
                'title' => $schema->string()->required(),
                'start_year' => $schema->integer()->nullable()->required(),
                'end_year' => $schema->integer()->nullable()->required(),
                'summary' => $schema->string()->nullable()->required(),
                'tags' => $schema->array()->items($schema->string())->required(),
                'entry_count' => $schema->integer()->description('Number of steps.')->required(),
                'atlas_url' => $schema->string()->required(),
            ]))->required(),
        ];
    }

    public function handle(Request $request, ListChroniclesAction $list): ResponseFactory
    {
        $input = $request->validate([
            'query' => ['required_without:tags', 'nullable', 'string', 'min:2', 'max:200'],
            'tags' => ['required_without:query', 'nullable', 'array', 'min:1', 'max:20'],
            'tags.*' => ['string', 'max:100'],
            'limit' => ['sometimes', 'nullable', 'integer', 'min:1', 'max:20'],
        ], [
            'query.required_without' => 'Give a query, tags, or both.',
            'tags.required_without' => 'Give a query, tags, or both.',
        ]);

        $page = $list([
            'search' => $input['query'] ?? null,
            'tags' => $input['tags'] ?? null,
            'sort' => 'impact',
            'per_page' => (int) ($input['limit'] ?? 10),
        ]);

        $rows = array_map(fn (Chronicle $c): array => [
            'slug' => $c->slug,
            'title' => $c->title,
            'start_year' => $c->start_year,
            'end_year' => $c->end_year,
            'summary' => Text::limit($c->description, EntityCards::SUMMARY_CHARS),
            'tags' => $c->tags->pluck('slug')->values()->all(),
            'entry_count' => (int) $c->entries_count,
            'atlas_url' => AtlasUrl::chronicle($c->slug),
        ], $page->items());

        $text = $rows === []
            ? 'No chronicles match. Try fewer tags or other words.'
            : sprintf('%d chronicle(s) of %d: %s.', count($rows), $page->total(), implode('; ', array_map(
                fn (array $r): string => $r['title'].' ('.($r['entry_count']).' steps'.(Text::dateLabel($r['start_year'], $r['end_year']) ? ', '.Text::dateLabel($r['start_year'], $r['end_year']) : '').')',
                array_slice($rows, 0, 8),
            )));

        return Reply::make($text, ['chronicles' => $rows]);
    }
}
