<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefProvider;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;

class ExportOhmRefIdsCommand extends Command
{
    protected $signature = 'pipeline:export-ohm-ref-ids
        {path : Output file, one type/id per line (the --ids-file of python -m pipeline ohm-links fetch)}';

    protected $description = 'Export the distinct OHM node/way/relation ids referenced by entity geo-refs';

    public function handle(): int
    {
        $path = (string) $this->argument('path');

        $lines = DB::table('entity_geo_refs')
            ->selectRaw('external_type::text AS type, external_id AS id')
            ->where('provider', GeoRefProvider::Ohm->value)
            ->whereIn('external_type', [
                GeoRefExternalType::Node->value,
                GeoRefExternalType::Way->value,
                GeoRefExternalType::Relation->value,
            ])
            ->whereRaw("external_id ~ '^[0-9]+$'")
            ->groupBy('external_type', 'external_id')
            ->orderBy('type')
            ->orderByRaw('external_id::numeric')
            ->get()
            ->map(fn (object $row): string => "{$row->type}/{$row->id}")
            ->all();

        File::ensureDirectoryExists(dirname($path));
        File::put($path, $lines === [] ? '' : implode("\n", $lines)."\n");

        $this->info('Wrote '.count($lines)." OHM ids to {$path}");

        return self::SUCCESS;
    }
}
