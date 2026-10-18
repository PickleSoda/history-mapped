<?php

declare(strict_types=1);

namespace Tests\Feature\ContentBundle;

use App\Actions\ContentBundle\ExportContentBundleAction;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\Scope\ExportScope;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * RefreshDatabase migrates a fresh DB, but with no wrapping test transaction: SET TRANSACTION must be the
 * first statement of a real top-level transaction. The scope matches nothing, so no rows are touched.
 */
class ContentExportSnapshotTest extends TestCase
{
    use RefreshDatabase;

    protected array $connectionsToTransact = [];

    public function test_export_runs_in_one_repeatable_read_read_only_transaction(): void
    {
        $this->assertSame(0, DB::transactionLevel());
        $statements = [];
        $levels = [];
        DB::listen(function ($q) use (&$statements, &$levels) {
            $statements[] = $q->sql;
            $levels[] = DB::transactionLevel();
        });

        $dir = sys_get_temp_dir().'/cb-snap-'.bin2hex(random_bytes(6));
        try {
            app(ExportContentBundleAction::class)($dir, ExportScope::parse(['entity:00000000-0000-4000-8000-000000000000']), Profile::Full);
        } finally {
            exec('rm -rf '.escapeshellarg($dir));
        }

        $this->assertSame('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY', $statements[0]);
        $this->assertGreaterThan(6, count($statements));
        $this->assertSame([1], array_values(array_unique($levels)), 'every query ran inside the one transaction');
        $this->assertSame(0, DB::transactionLevel());
    }
}
