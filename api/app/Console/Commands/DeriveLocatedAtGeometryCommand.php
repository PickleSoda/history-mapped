<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\Entity\DeriveLocatedAtGeometryAction;
use App\Enums\EntityGroup;
use Illuminate\Console\Command;

class DeriveLocatedAtGeometryCommand extends Command
{
    protected $signature = 'geometry:derive-located-at
        {--apply : Write the derived geometry periods (default is a dry run)}
        {--group=* : Entity group(s) to place: EVENT, PLACE (default both)}
        {--precise-only : Only borrow a PLACE target\'s point, never a polity\'s}
        {--entity-id= : Limit to one entity id}
        {--sample=0 : Print up to N planned rows}';

    protected $description = 'Additively place unmapped events/places at the point of their located_at target (dry run unless --apply)';

    public function handle(DeriveLocatedAtGeometryAction $derive): int
    {
        $groups = [];
        $requested = (array) $this->option('group');
        foreach ($requested !== [] ? $requested : ['EVENT', 'PLACE'] as $value) {
            $group = EntityGroup::tryFrom(strtoupper((string) $value));
            if ($group === null || ! in_array($group, DeriveLocatedAtGeometryAction::SUPPORTED_GROUPS, true)) {
                $this->error("Unsupported --group={$value} (use EVENT or PLACE)");

                return self::INVALID;
            }
            $groups[] = $group;
        }

        $entityId = $this->option('entity-id');
        $plan = $derive->plan(
            array_values(array_unique($groups, SORT_REGULAR)),
            (bool) $this->option('precise-only'),
            is_string($entityId) && $entityId !== '' ? $entityId : null,
        );
        $candidates = $plan['candidates'];

        $byType = [];
        foreach ($candidates as $row) {
            $key = "{$row->entity_group}|{$row->entity_type}";
            $byType[$key] ??= [$row->entity_group, $row->entity_type, 0, 0, 0];
            $byType[$key][2]++;
            $byType[$key][$row->confidence === 'medium' ? 3 : 4]++;
        }
        ksort($byType);

        $apply = (bool) $this->option('apply');
        $this->info(($apply ? '[APPLY]' : '[DRY-RUN]').' located_at geometry derivation: '.count($candidates).' period(s) planned');
        $this->table(['group', 'entity_type', 'periods', 'medium (place target)', 'low (polity target)'],
            array_map(fn (array $r): array => array_map('strval', $r), array_values($byType)));
        $this->line(sprintf(
            'skipped: own_point=%d (run entity:backfill) no_year=%d polity_target=%d (--precise-only)',
            $plan['skipped']['own_point'], $plan['skipped']['no_year'], $plan['skipped']['polity_target'],
        ));

        $sample = max(0, (int) $this->option('sample'));
        foreach (array_slice($candidates, 0, $sample) as $row) {
            $this->line(sprintf('  %s [%s] %s..%s -> %s [%s, %s]', $row->name, $row->entity_type,
                $row->start_year, $row->end_year ?? '', $row->target_name, $row->target_type, $row->point_source));
        }

        if (! $apply) {
            $this->comment('Dry run: nothing written. Re-run with --apply to insert.');

            return self::SUCCESS;
        }

        $inserted = $derive->apply($candidates);
        $this->info("Inserted {$inserted} geometry period(s) (created_by=".DeriveLocatedAtGeometryAction::CREATED_BY.').');

        return self::SUCCESS;
    }
}
