<?php

declare(strict_types=1);

namespace App\Support;

use App\Enums\ContributionTargetType;
use App\Models\Contribution;
use Illuminate\Support\Str;

/**
 * Reads of a `create` contribution's payload for lists and pages: a label, a
 * one-line summary, and the proposal as label/value rows.
 *
 * Payload shapes (written by ProposeEntityAction / ProposeRelationshipAction):
 *   entity:       {entity: {name, entity_type, entity_group, ...}, possible_duplicates: [...]}
 *   relationship: {relationship: {source: {entity_id|contribution_id, label}, target: {...},
 *                  relationship_type, temporal_start, temporal_end, description, source_citations}}
 */
final class ContributionProposal
{
    public static function label(Contribution $c): string
    {
        $p = $c->payload ?? [];

        if ($c->target_type === ContributionTargetType::Relationship) {
            $r = $p['relationship'] ?? [];

            return sprintf(
                '%s → %s (%s)',
                $r['source']['label'] ?? '?',
                $r['target']['label'] ?? '?',
                self::humanise($r['relationship_type'] ?? 'related'),
            );
        }

        return (string) ($p['entity']['name'] ?? 'New entity');
    }

    /** "New person, 1066–1100" style one-liner. */
    public static function summary(Contribution $c): string
    {
        $p = $c->payload ?? [];

        if ($c->target_type === ContributionTargetType::Relationship) {
            return 'New relationship: '.self::label($c);
        }

        $e = $p['entity'] ?? [];
        $years = array_filter([$e['temporal_start'] ?? null, $e['temporal_end'] ?? null], fn ($y) => $y !== null && $y !== '');
        $when = $years === [] ? '' : ', '.implode('–', $years);

        return 'New '.self::humanise($e['entity_type'] ?? 'entity').': '.($e['name'] ?? '?').$when;
    }

    /**
     * The proposal as ordered label => value pairs for the admin page.
     *
     * @return list<array{label: string, value: string}>
     */
    public static function rows(Contribution $c): array
    {
        $p = $c->payload ?? [];
        $rows = [];
        $add = function (string $label, mixed $value) use (&$rows): void {
            if ($value === null || $value === '' || $value === []) {
                return;
            }
            $rows[] = ['label' => $label, 'value' => is_array($value) ? implode('; ', array_map(self::cite(...), $value)) : (string) $value];
        };

        if ($c->target_type === ContributionTargetType::Relationship) {
            $r = $p['relationship'] ?? [];
            $add('From', self::end($r['source'] ?? []));
            $add('Type', self::humanise($r['relationship_type'] ?? ''));
            $add('To', self::end($r['target'] ?? []));
            $add('Starts', $r['temporal_start'] ?? null);
            $add('Ends', $r['temporal_end'] ?? null);
            $add('Description', $r['description'] ?? null);
            $add('Sources', $r['source_citations'] ?? null);

            return $rows;
        }

        $e = $p['entity'] ?? [];
        $add('Name', $e['name'] ?? null);
        $add('Type', self::humanise($e['entity_type'] ?? ''));
        $add('Other names', $e['alternative_names'] ?? null);
        $add('Starts', $e['temporal_start'] ?? null);
        $add('Ends', $e['temporal_end'] ?? null);
        $add('Place', $e['location_name'] ?? null);
        $coords = $e['geojson']['coordinates'] ?? null;
        $add('Coordinates', is_array($coords) && count($coords) >= 2 ? sprintf('%s, %s (lat, lng)', $coords[1], $coords[0]) : null);
        $add('Wikidata', $e['wikidata_id'] ?? null);
        $add('Summary', $e['summary'] ?? null);
        $add('Description', $e['description'] ?? null);
        $add('Sources', $e['source_citations'] ?? null);

        return $rows;
    }

    /** @param  array{entity_id?: string, contribution_id?: int, label?: string}  $end */
    private static function end(array $end): string
    {
        $label = (string) ($end['label'] ?? '?');

        return isset($end['contribution_id']) ? $label.' (pending proposal #'.$end['contribution_id'].')' : $label;
    }

    /** @param  array<string, mixed>|string  $citation */
    private static function cite(mixed $citation): string
    {
        if (! is_array($citation)) {
            return (string) $citation;
        }

        return trim(($citation['title'] ?? '').' '.($citation['url'] ?? ''));
    }

    private static function humanise(string $value): string
    {
        return (string) Str::of($value)->replace('_', ' ');
    }
}
