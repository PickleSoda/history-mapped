<?php

namespace App\Ai\Tools;

use App\Ai\Tools\Concerns\ComputesPlacement;
use App\Enums\EntityType;
use App\Services\Geo\PlaceFinder;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Ai\Tools\Request;
use Stringable;
use Throwable;

class FindPlace extends AgentTool
{
    use ComputesPlacement;

    private const SOURCES = ['any', 'entities', 'ohm'];

    public function __construct(
        private PlaceFinder $places,
    ) {}

    public static function name(): string
    {
        return 'find_place';
    }

    public function description(): string
    {
        return 'Look up the coordinates of a named place (city, island, river mouth, battle site…) to anchor a placement. '
            .'Searches our entities (names and alternative names), then the OpenHistoricalMap gazetteer. '
            .'Each candidate has lon/lat and a precision; "approximate" means the point is a generic fallback centroid — pick an "exact" candidate instead. '
            .'Use the modern or most common name, and pass year to prefer places that existed then.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'name' => $schema->string()->description('Place name, e.g. "Ostia" or "Carthage".')->required(),
            'year' => $schema->integer()->description('Optional year (negative = BCE): prefer places that existed then.'),
            'entity_type' => $schema->string()
                ->enum(array_map(fn (EntityType $t) => $t->value, EntityType::cases()))
                ->description('Optional: only our entities of this type, e.g. city.'),
            'source' => $schema->string()
                ->enum(self::SOURCES)
                ->description('any (default) = our entities, plus OpenHistoricalMap when none matches the name exactly; entities = ours only; ohm = OpenHistoricalMap only.'),
        ];
    }

    /** Read-only: returns candidates directly, no proposal staged. */
    public function handle(Request $request): Stringable|string
    {
        $name = trim((string) ($request['name'] ?? ''));
        if ($name === '') {
            return $this->failure('Give the place name to look up.');
        }

        $source = in_array($request['source'] ?? null, self::SOURCES, true) ? $request['source'] : 'any';
        $year = is_numeric($request['year'] ?? null) ? (int) $request['year'] : null;
        $type = EntityType::tryFrom((string) ($request['entity_type'] ?? ''))?->value;

        $candidates = $source === 'ohm' ? [] : $this->places->searchEntities($name, $type, $year);
        $warnings = [];

        $goodMatch = collect($candidates)->contains(
            fn (array $c) => ($c['exact_name'] ?? false) && $c['precision'] === 'exact',
        );
        if ($source === 'ohm' || ($source === 'any' && ! $goodMatch)) {
            try {
                $candidates = [...$candidates, ...$this->places->searchOhm($name)];
            } catch (Throwable $e) {
                report($e);
                $warnings[] = 'The OpenHistoricalMap gazetteer could not be reached, so only our own entities were searched.';
            }
        }

        if ($candidates === []) {
            return json_encode(array_filter([
                'query' => $name,
                'candidates' => [],
                'message' => "Nothing found for '{$name}'. Try another spelling, the modern name, or a larger place nearby.",
                'warnings' => $warnings ?: null,
            ], fn ($v) => $v !== null), JSON_THROW_ON_ERROR);
        }

        return json_encode(array_filter([
            'query' => $name,
            'candidates' => $candidates,
            'warnings' => $warnings ?: null,
            'next' => 'Use the best candidate\'s lon/lat (or entity_id) as the anchor for point_from_offset, point_between or nearest_coast — or pass lon/lat straight to set_entity_location.',
        ], fn ($v) => $v !== null), JSON_THROW_ON_ERROR);
    }
}
