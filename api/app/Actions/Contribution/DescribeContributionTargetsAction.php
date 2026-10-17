<?php

declare(strict_types=1);

namespace App\Actions\Contribution;

use App\Enums\ContributionTargetType;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Contribution;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Support\ContributionFields;
use Illuminate\Support\Collection;
use Illuminate\Support\Str;

/**
 * Human labels, links and live editable-field values for the records a page of
 * contributions edits, in one query per target type. Returns
 * `"{type}:{id}" => {label, admin_url, public_url, fields}`; a deleted target
 * has no key. `fields` lets callers flag stale contributions in bulk.
 */
class DescribeContributionTargetsAction
{
    /**
     * @param  iterable<Contribution>  $contributions
     * @return array<string, array{label: string, admin_url: string, public_url: string, fields: array<string, string|null>}>
     */
    public function __invoke(iterable $contributions): array
    {
        $idsByType = collect($contributions)
            ->groupBy(fn (Contribution $c) => $c->target_type->value)
            ->map(fn (Collection $group) => $group->pluck('target_id')->unique()->values()->all());

        $out = [];
        foreach ($idsByType as $type => $ids) {
            $described = match (ContributionTargetType::from($type)) {
                ContributionTargetType::Entity => $this->entities($ids),
                ContributionTargetType::Relationship => $this->relationships($ids),
                ContributionTargetType::Chronicle => $this->chronicles($ids),
                ContributionTargetType::ChronicleEntry => $this->entries($ids),
            };
            foreach ($described as $id => $d) {
                $out["{$type}:{$id}"] = $d;
            }
        }

        return $out;
    }

    public static function key(Contribution $c): string
    {
        return "{$c->target_type->value}:{$c->target_id}";
    }

    /**
     * @param  list<string>  $ids
     * @return array<string, array{label: string, admin_url: string, public_url: string, fields: array<string, string|null>}>
     */
    private function entities(array $ids): array
    {
        return Entity::query()->whereKey($ids)
            ->with(['aliases' => fn ($q) => $q->select(['alias_id', 'entity_id', 'name'])])
            ->get(['entity_id', 'name', 'summary', 'significance'])
            ->mapWithKeys(fn (Entity $e) => [$e->entity_id => [
                'label' => $e->name,
                'admin_url' => url('/entities/'.rawurlencode($e->entity_id)),
                'public_url' => self::atlas(['sel' => $e->entity_id, 'full' => '1']),
                'fields' => [
                    ...$e->only(['name', 'summary', 'significance']),
                    'aliases' => ContributionFields::listText($e->aliases->pluck('name')),
                ],
            ]])
            ->all();
    }

    /**
     * @param  list<string>  $ids
     * @return array<string, array{label: string, admin_url: string, public_url: string, fields: array<string, string|null>}>
     */
    private function relationships(array $ids): array
    {
        return EntityRelationship::query()->whereKey($ids)
            ->with(['sourceEntity:entity_id,name', 'targetEntity:entity_id,name'])
            ->get()
            ->mapWithKeys(fn (EntityRelationship $r) => [$r->relationship_id => [
                'label' => sprintf(
                    '%s → %s (%s)',
                    $r->sourceEntity->name ?? '?',
                    $r->targetEntity->name ?? '?',
                    Str::of($r->relationship_type?->value ?? 'related')->replace('_', ' '),
                ),
                'admin_url' => url('/entities/'.rawurlencode($r->source_entity_id)),
                'public_url' => self::atlas(['sel' => $r->source_entity_id, 'full' => '1']),
                'fields' => ['description' => $r->description],
            ]])
            ->all();
    }

    /**
     * @param  list<string>  $ids
     * @return array<string, array{label: string, admin_url: string, public_url: string, fields: array<string, string|null>}>
     */
    private function chronicles(array $ids): array
    {
        return Chronicle::query()->whereKey($ids)->get(['chronicle_id', 'slug', 'title'])
            ->mapWithKeys(fn (Chronicle $c) => [$c->chronicle_id => [
                'label' => $c->title,
                'admin_url' => url('/chronicles/'.rawurlencode($c->slug)),
                'public_url' => self::atlas(['chron' => $c->slug, 'full' => '1']),
                'fields' => ['title' => $c->title],
            ]])
            ->all();
    }

    /**
     * @param  list<string>  $ids
     * @return array<string, array{label: string, admin_url: string, public_url: string, fields: array<string, string|null>}>
     */
    private function entries(array $ids): array
    {
        $entries = ChronicleEntry::query()->whereKey($ids)
            ->with('chronicle:chronicle_id,slug,title')
            ->get(['entry_id', 'chronicle_id', 'sequence_order', 'narrative_text']);

        // The atlas addresses a step by its 0-based position in the tour.
        $positions = [];
        $seen = [];
        ChronicleEntry::query()
            ->whereIn('chronicle_id', $entries->pluck('chronicle_id')->unique())
            ->orderBy('chronicle_id')
            ->orderBy('sequence_order')
            ->get(['entry_id', 'chronicle_id'])
            ->each(function (ChronicleEntry $step) use (&$positions, &$seen): void {
                $positions[$step->entry_id] = $seen[$step->chronicle_id] = ($seen[$step->chronicle_id] ?? -1) + 1;
            });

        return $entries->mapWithKeys(function (ChronicleEntry $e) use ($positions) {
            $step = (int) ($positions[$e->entry_id] ?? 0);
            $chronicle = $e->chronicle;

            return [$e->entry_id => [
                'label' => sprintf('%s · step %d', $chronicle->title ?? 'Chronicle', $step + 1),
                'admin_url' => $chronicle ? url('/chronicles/'.rawurlencode($chronicle->slug)) : url('/chronicles'),
                'public_url' => $chronicle
                    ? self::atlas(['chron' => $chronicle->slug, 'step' => (string) $step, 'full' => '1'])
                    : self::atlas([]),
                'fields' => ['narrative_text' => $e->narrative_text],
            ]];
        })->all();
    }

    /** @param  array<string, string>  $params */
    private static function atlas(array $params): string
    {
        $base = config('app.frontend_url');

        return $params === [] ? $base.'/' : $base.'/?'.http_build_query($params);
    }
}
