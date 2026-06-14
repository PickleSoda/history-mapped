# Standalone Relationship Resolution and Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `target_not_found` retryability in `ResolveRelationshipsJob`, add `pipeline:resolve-relationships` and `pipeline:report-relationship-hints` commands, and add end-to-end event-hub import verification.

**Architecture:** Minimal changes to the existing job (only `markHint` semantics), plus two thin read-only/reporting commands and one resolution orchestrator. No schema changes.

**Tech Stack:** Laravel 13, PHP 8.4, PHPUnit, existing `pipeline_relationship_hints` staging table.

---

## File Structure

- Modify: `api/app/Jobs/ResolveRelationshipsJob.php`
  - Change `markHint` so `target_not_found` keeps `resolved=false`
  - Add `resolveAll()` method for cross-batch resolution
- Create: `api/app/Console/Commands/ResolvePipelineRelationshipsCommand.php`
  - Thin wrapper around `ResolveRelationshipsJob` with batch-scoped or global unresolved resolution
- Create: `api/app/Console/Commands/ReportPipelineRelationshipHintsCommand.php`
  - Read-only audit of staging table + embedded hints
- Create: `api/tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php`
  - Command behavior: single batch, all batches, dry-run, sync, idempotency
- Create: `api/tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php`
  - Reporting behavior: counts, samples, empty table
- Create: `api/tests/Feature/Feature/PipelineEventHubImportTest.php`
  - End-to-end battle-cluster import + resolution + graph verification
- Modify: `api/tests/Feature/Feature/ResolveRelationshipsJobTest.php`
  - Update `target_not_found` assertion from `resolved=true` to `resolved=false`
- Modify: `docs/implementation-docs/data_pipeline_architecture.md`
  - Document the new commands in the Laravel import section

---

### Task 1: Fix Retryability in ResolveRelationshipsJob

**Files:**
- Modify: `api/app/Jobs/ResolveRelationshipsJob.php`
- Modify: `api/tests/Feature/Feature/ResolveRelationshipsJobTest.php`

- [ ] **Step 1: Update `markHint` to leave `target_not_found` unresolved**

In `api/app/Jobs/ResolveRelationshipsJob.php`, change `markHint`:

```php
private function markHint(int $hintId, string $note): void
{
    $isTerminal = !in_array($note, ['target_not_found'], true);
    DB::table('pipeline_relationship_hints')
        ->where('id', $hintId)
        ->update([
            'resolved' => $isTerminal,
            'resolution_note' => $note,
        ]);
}
```

- [ ] **Step 2: Add `resolveAll()` method for cross-batch mode**

Add a public method:

```php
public function resolveAll(CreateRelationshipAction $createRelationship): void
{
    $batchIds = DB::table('pipeline_relationship_hints')
        ->where('resolved', false)
        ->distinct()
        ->pluck('batch_id');

    foreach ($batchIds as $batchId) {
        Log::info("[Pipeline] Resolving batch: {$batchId}");
        (new self($batchId))->handle($createRelationship);
    }
}
```

- [ ] **Step 3: Update existing test expectations**

In `api/tests/Feature/Feature/ResolveRelationshipsJobTest.php`, change:

```php
// From:
'resolved' => true,
'resolution_note' => 'target_not_found',

// To:
'resolved' => false,
'resolution_note' => 'target_not_found',
```

- [ ] **Step 4: Add retryability test**

Add a new test method:

```php
public function test_target_not_found_is_retryable(): void
{
    $source = Entity::factory()->create(['wikidata_id' => 'Q100']);
    $id = $this->seedHint($source, 'Q200', 'part_of');

    $this->runJob();

    $this->assertDatabaseHas('pipeline_relationship_hints', [
        'id' => $id,
        'resolved' => false,
        'resolution_note' => 'target_not_found',
    ]);

    // Import the missing target
    $target = Entity::factory()->create(['wikidata_id' => 'Q200']);

    // Re-run the job
    $this->runJob();

    $this->assertDatabaseHas('relationships', [
        'source_entity_id' => $source->entity_id,
        'target_entity_id' => $target->entity_id,
        'relationship_type' => 'part_of',
    ]);

    $this->assertDatabaseHas('pipeline_relationship_hints', [
        'id' => $id,
        'resolved' => true,
        'resolution_note' => 'created',
    ]);
}
```

- [ ] **Step 5: Run focused job tests**

Run:
```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ResolveRelationshipsJobTest.php --compact
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/Jobs/ResolveRelationshipsJob.php api/tests/Feature/Feature/ResolveRelationshipsJobTest.php
git commit -m "fix: make target_not_found retryable in relationship resolution"
```

---

### Task 2: Add ResolvePipelineRelationshipsCommand

**Files:**
- Create: `api/app/Console/Commands/ResolvePipelineRelationshipsCommand.php`
- Create: `api/tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php`

- [ ] **Step 1: Write failing command test**

Create `api/tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php`:

```php
<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class ResolvePipelineRelationshipsCommandTest extends TestCase
{
    use RefreshDatabase;

    private function seedHint(Entity $source, string $targetWikidataId, string $type, string $batchId): int
    {
        return DB::table('pipeline_relationship_hints')->insertGetId([
            'source_entity_id' => $source->entity_id,
            'relationship_type' => $type,
            'target_wikidata_id' => $targetWikidataId,
            'target_label' => 'Label',
            'batch_id' => $batchId,
            'resolved' => false,
        ]);
    }

    public function test_resolves_single_batch(): void
    {
        $batchId = 'batch-a';
        $source = Entity::factory()->create(['wikidata_id' => 'Q1']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q2']);
        $this->seedHint($source, 'Q2', 'allied_with', $batchId);

        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId])
            ->assertSuccessful();

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
        ]);
    }

    public function test_resolves_all_unresolved_batches_when_no_batch_id_given(): void
    {
        $batchA = 'batch-a';
        $batchB = 'batch-b';
        $sourceA = Entity::factory()->create(['wikidata_id' => 'Q10']);
        $sourceB = Entity::factory()->create(['wikidata_id' => 'Q11']);
        $targetA = Entity::factory()->create(['wikidata_id' => 'Q20']);
        $targetB = Entity::factory()->create(['wikidata_id' => 'Q21']);
        $this->seedHint($sourceA, 'Q20', 'part_of', $batchA);
        $this->seedHint($sourceB, 'Q21', 'part_of', $batchB);

        $this->artisan('pipeline:resolve-relationships')
            ->assertSuccessful();

        $this->assertDatabaseCount('relationships', 2);
    }

    public function test_dry_run_does_not_create_relationships(): void
    {
        $batchId = 'batch-c';
        $source = Entity::factory()->create(['wikidata_id' => 'Q30']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q31']);
        $this->seedHint($source, 'Q31', 'allied_with', $batchId);

        $this->artisan('pipeline:resolve-relationships', [
            'batchId' => $batchId,
            '--dry-run' => true,
        ])->assertSuccessful();

        $this->assertDatabaseCount('relationships', 0);
    }

    public function test_idempotent_rerun(): void
    {
        $batchId = 'batch-d';
        $source = Entity::factory()->create(['wikidata_id' => 'Q40']);
        $target = Entity::factory()->create(['wikidata_id' => 'Q41']);
        $this->seedHint($source, 'Q41', 'allied_with', $batchId);

        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId])->assertSuccessful();
        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId])->assertSuccessful();

        $this->assertDatabaseCount('relationships', 1);
    }
}
```

- [ ] **Step 2: Run test to verify failure**

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php --compact
```
Expected: FAIL because the command does not exist.

- [ ] **Step 3: Implement the command**

Create `api/app/Console/Commands/ResolvePipelineRelationshipsCommand.php`:

```php
<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Jobs\ResolveRelationshipsJob;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

class ResolvePipelineRelationshipsCommand extends Command
{
    protected $signature = 'pipeline:resolve-relationships
        {batchId? : Resolve hints for this batch; omit to resolve all unresolved hints}
        {--sync : Run synchronously instead of dispatching a job}
        {--dry-run : Show counts without creating relationships}';

    protected $description = 'Resolve pipeline relationship hints into relationship records';

    public function handle(): int
    {
        $batchId = $this->argument('batchId');
        $sync = (bool) $this->option('sync');
        $dryRun = (bool) $this->option('dry-run');

        if ($dryRun) {
            return $this->runDryRun($batchId);
        }

        if ($batchId !== null) {
            return $this->resolveBatch((string) $batchId, $sync);
        }

        return $this->resolveAll($sync);
    }

    private function resolveBatch(string $batchId, bool $sync): int
    {
        $count = DB::table('pipeline_relationship_hints')
            ->where('batch_id', $batchId)
            ->where('resolved', false)
            ->count();

        if ($count === 0) {
            $this->warn("No unresolved hints for batch: {$batchId}");

            return self::SUCCESS;
        }

        $this->info("Resolving {$count} hints for batch: {$batchId}");

        $job = new ResolveRelationshipsJob($batchId);

        if ($sync) {
            app()->call([$job, 'handle']);
        } else {
            dispatch($job);
            $this->info('Job dispatched.');
        }

        return self::SUCCESS;
    }

    private function resolveAll(bool $sync): int
    {
        $batchIds = DB::table('pipeline_relationship_hints')
            ->where('resolved', false)
            ->distinct()
            ->pluck('batch_id');

        if ($batchIds->isEmpty()) {
            $this->warn('No unresolved hints found.');

            return self::SUCCESS;
        }

        $this->info("Resolving hints for {$batchIds->count()} batch(es)...");

        foreach ($batchIds as $batchId) {
            $job = new ResolveRelationshipsJob($batchId);

            if ($sync) {
                app()->call([$job, 'handle']);
            } else {
                dispatch($job);
            }
        }

        $this->info('Done.');

        return self::SUCCESS;
    }

    private function runDryRun(?string $batchId): int
    {
        $query = DB::table('pipeline_relationship_hints')
            ->select('batch_id', 'resolution_note', DB::raw('count(*) as total'))
            ->where('resolved', false);

        if ($batchId !== null) {
            $query->where('batch_id', $batchId);
        }

        $rows = $query->groupBy('batch_id', 'resolution_note')->get();

        if ($rows->isEmpty()) {
            $this->warn('No unresolved hints found.');

            return self::SUCCESS;
        }

        $this->table(
            ['Batch', 'Resolution Note', 'Count'],
            $rows->map(fn ($r) => [$r->batch_id, $r->resolution_note, $r->total])->toArray()
        );

        return self::SUCCESS;
    }
}
```

- [ ] **Step 4: Run command tests**

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php --compact
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/Console/Commands/ResolvePipelineRelationshipsCommand.php api/tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php
git commit -m "feat: add pipeline:resolve-relationships command"
```

---

### Task 3: Add ReportPipelineRelationshipHintsCommand

**Files:**
- Create: `api/app/Console/Commands/ReportPipelineRelationshipHintsCommand.php`
- Create: `api/tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php`

- [ ] **Step 1: Write failing command test**

Create `api/tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php`:

```php
<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class ReportPipelineRelationshipHintsCommandTest extends TestCase
{
    use RefreshDatabase;

    private function seedHint(Entity $source, string $targetWikidataId, string $type, string $batchId, bool $resolved = false, ?string $note = null): void
    {
        DB::table('pipeline_relationship_hints')->insert([
            'source_entity_id' => $source->entity_id,
            'relationship_type' => $type,
            'target_wikidata_id' => $targetWikidataId,
            'target_label' => 'Label',
            'batch_id' => $batchId,
            'resolved' => $resolved,
            'resolution_note' => $note,
        ]);
    }

    public function test_reports_counts_by_batch(): void
    {
        $batch = 'batch-r';
        $source = Entity::factory()->create();
        $this->seedHint($source, 'Q1', 'part_of', $batch, true, 'created');
        $this->seedHint($source, 'Q2', 'part_of', $batch, false, 'target_not_found');

        $this->artisan('pipeline:report-relationship-hints', ['batchId' => $batch])
            ->assertSuccessful()
            ->expectsOutputToContain('Target Not Found');
    }

    public function test_reports_all_batches_when_no_batch_id_given(): void
    {
        $source = Entity::factory()->create();
        $this->seedHint($source, 'Q1', 'part_of', 'batch-a', false, 'target_not_found');
        $this->seedHint($source, 'Q2', 'part_of', 'batch-b', true, 'created');

        $this->artisan('pipeline:report-relationship-hints')
            ->assertSuccessful();
    }

    public function test_handles_empty_table(): void
    {
        $this->artisan('pipeline:report-relationship-hints')
            ->assertSuccessful()
            ->expectsOutputToContain('No hints found');
    }
}
```

- [ ] **Step 2: Run test to verify failure**

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php --compact
```
Expected: FAIL because the command does not exist.

- [ ] **Step 3: Implement the command**

Create `api/app/Console/Commands/ReportPipelineRelationshipHintsCommand.php`:

```php
<?php

declare(strict_types=1);

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

class ReportPipelineRelationshipHintsCommand extends Command
{
    protected $signature = 'pipeline:report-relationship-hints
        {batchId? : Report for this batch only; omit for all batches}
        {--limit=10 : Sample size per class}';

    protected $description = 'Report pipeline relationship hint status';

    public function handle(): int
    {
        $batchId = $this->argument('batchId');
        $limit = (int) $this->option('limit');

        $this->reportSummary($batchId);
        $this->reportRetryableSamples($batchId, $limit);
        $this->reportEmbeddedHints($limit);

        return self::SUCCESS;
    }

    private function reportSummary(?string $batchId): void
    {
        $query = DB::table('pipeline_relationship_hints')
            ->select('batch_id', 'resolution_note', DB::raw('count(*) as total'))
            ->groupBy('batch_id', 'resolution_note');

        if ($batchId !== null) {
            $query->where('batch_id', $batchId);
        }

        $rows = $query->get();

        if ($rows->isEmpty()) {
            $this->warn('No hints found.');

            return;
        }

        $this->info('Summary by batch and resolution note:');
        $this->table(
            ['Batch', 'Resolution Note', 'Count'],
            $rows->map(fn ($r) => [$r->batch_id, $r->resolution_note, $r->total])->toArray()
        );
    }

    private function reportRetryableSamples(?string $batchId, int $limit): void
    {
        $query = DB::table('pipeline_relationship_hints')
            ->where('resolved', false)
            ->where('resolution_note', 'target_not_found')
            ->limit($limit);

        if ($batchId !== null) {
            $query->where('batch_id', $batchId);
        }

        $rows = $query->get();

        if ($rows->isEmpty()) {
            return;
        }

        $this->newLine();
        $this->info("Retryable samples (target_not_found, limit {$limit}):");

        foreach ($rows as $row) {
            $sourceName = DB::table('entities')->where('entity_id', $row->source_entity_id)->value('name');
            $this->line("  - {$row->target_wikidata_id} (source: {$sourceName}) → type: {$row->relationship_type}");
        }
    }

    private function reportEmbeddedHints(int $limit): void
    {
        $entities = DB::table('entities')
            ->whereRaw('jsonb_exists(attributes, ?)', ['_relationship_hints'])
            ->select('entity_id', 'name', 'attributes')
            ->limit($limit)
            ->get();

        if ($entities->isEmpty()) {
            return;
        }

        $this->newLine();
        $this->info('Embedded hints still in attributes:');

        foreach ($entities as $entity) {
            $attrs = json_decode($entity->attributes, true) ?? [];
            $hintCount = count($attrs['_relationship_hints'] ?? []);
            $this->line("  - Entity: {$entity->name} ({$entity->entity_id}) → {$hintCount} hint(s)");
        }
    }
}
```

- [ ] **Step 4: Run command tests**

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php --compact
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/Console/Commands/ReportPipelineRelationshipHintsCommand.php api/tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php
git commit -m "feat: add pipeline:report-relationship-hints command"
```

---

### Task 4: Add End-to-End Event Hub Import Test

**Files:**
- Create: `api/tests/Feature/Feature/PipelineEventHubImportTest.php`

- [ ] **Step 1: Write the failing test**

Create `api/tests/Feature/Feature/PipelineEventHubImportTest.php`:

```php
<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class PipelineEventHubImportTest extends TestCase
{
    use RefreshDatabase;

    public function test_end_to_end_battle_cluster_import_and_resolution(): void
    {
        $battleId = 'Q12345';
        $armyAId = 'Q111';
        $armyBId = 'Q222';
        $commanderAId = 'Q333';
        $commanderBId = 'Q444';
        $placeId = 'Q555';

        // Seed entities as if imported from JSONL
        $battle = Entity::factory()->create([
            'wikidata_id' => $battleId,
            'name' => 'Battle of Gaugamela',
            'entity_type' => 'event_battle',
        ]);
        $armyA = Entity::factory()->create(['wikidata_id' => $armyAId, 'name' => 'Macedonian Army']);
        $armyB = Entity::factory()->create(['wikidata_id' => $armyBId, 'name' => 'Persian Army']);
        $commanderA = Entity::factory()->create(['wikidata_id' => $commanderAId, 'name' => 'Alexander']);
        $commanderB = Entity::factory()->create(['wikidata_id' => $commanderBId, 'name' => 'Darius III']);
        $place = Entity::factory()->create(['wikidata_id' => $placeId, 'name' => 'Gaugamela']);

        // Stage hints
        $batchId = 'test-battle-cluster';
        $hints = [
            [$armyA->entity_id, $battleId, 'participated_in'],
            [$armyB->entity_id, $battleId, 'participated_in'],
            [$commanderA->entity_id, $armyAId, 'commanded'],
            [$commanderA->entity_id, $battleId, 'victorious_at'],
            [$commanderB->entity_id, $battleId, 'defeated_at'],
            [$battle->entity_id, $placeId, 'located_at'],
        ];

        foreach ($hints as [$sourceId, $targetQid, $type]) {
            DB::table('pipeline_relationship_hints')->insert([
                'source_entity_id' => $sourceId,
                'relationship_type' => $type,
                'target_wikidata_id' => $targetQid,
                'batch_id' => $batchId,
                'resolved' => false,
            ]);
        }

        // Run resolution
        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId, '--sync' => true])
            ->assertSuccessful();

        // Assert graph edges
        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $armyA->entity_id,
            'target_entity_id' => $battle->entity_id,
            'relationship_type' => 'participated_in',
        ]);
        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $commanderA->entity_id,
            'target_entity_id' => $battle->entity_id,
            'relationship_type' => 'victorious_at',
        ]);
        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $battle->entity_id,
            'target_entity_id' => $place->entity_id,
            'relationship_type' => 'located_at',
        ]);

        // Assert no hints remain unresolved
        $this->assertDatabaseCount('pipeline_relationship_hints', 6);
        $this->assertDatabaseMissing('pipeline_relationship_hints', [
            'batch_id' => $batchId,
            'resolved' => false,
        ]);
    }

    public function test_late_arriving_target_entity_gets_resolved_on_retry(): void
    {
        $batchId = 'test-late-target';
        $source = Entity::factory()->create(['wikidata_id' => 'Q900']);

        DB::table('pipeline_relationship_hints')->insert([
            'source_entity_id' => $source->entity_id,
            'relationship_type' => 'allied_with',
            'target_wikidata_id' => 'Q999',
            'batch_id' => $batchId,
            'resolved' => false,
        ]);

        // First run: target missing
        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId, '--sync' => true])
            ->assertSuccessful();

        $this->assertDatabaseCount('relationships', 0);

        // Import the missing target
        $target = Entity::factory()->create(['wikidata_id' => 'Q999']);

        // Second run: target now exists
        $this->artisan('pipeline:resolve-relationships', ['batchId' => $batchId, '--sync' => true])
            ->assertSuccessful();

        $this->assertDatabaseHas('relationships', [
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'allied_with',
        ]);
    }
}
```

- [ ] **Step 2: Run test to verify failure**

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/PipelineEventHubImportTest.php --compact
```
Expected: FAIL if the new commands are not fully wired; otherwise PASS.

- [ ] **Step 3: Run the full feature suite**

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ResolveRelationshipsJobTest.php tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php tests/Feature/Feature/PipelineEventHubImportTest.php --compact
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add api/tests/Feature/Feature/PipelineEventHubImportTest.php
git commit -m "test: add end-to-end event hub pipeline import verification"
```

---

### Task 5: Update Documentation

**Files:**
- Modify: `docs/implementation-docs/data_pipeline_architecture.md`

- [ ] **Step 1: Add the new commands to the Laravel import section**

Find the existing "Laravel-side import and embeddings" section and add:

```markdown
### Relationship resolution

After importing entities, resolve relationship hints:

```bash
# Resolve all unresolved hints across all batches
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:resolve-relationships

# Resolve one specific batch
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:resolve-relationships pipeline-20260530-120000

# Dry-run to preview counts without creating relationships
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:resolve-relationships --dry-run

# Report hint status
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:report-relationship-hints
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/implementation-docs/data_pipeline_architecture.md
git commit -m "docs: document relationship resolution and reporting commands"
```

---

### Task 6: Final Verification

- [ ] **Step 1: Run the full Laravel feature suite**

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ --compact
```
Expected: PASS (or only pre-existing unrelated failures).

- [ ] **Step 2: Verify command registration**

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan list | grep pipeline:resolve-relationships
docker compose -f docker/docker-compose.yml exec app php artisan list | grep pipeline:report-relationship-hints
```
Expected: both commands listed.

- [ ] **Step 3: Commit final verification**

```bash
git add docs/implementation-docs/data_pipeline_architecture.md
git commit -m "docs: finalize relationship resolution runbook"
```

---

## Acceptance Criteria

- `target_not_found` hints remain `resolved=false` and can be resolved on re-run.
- `pipeline:resolve-relationships` resolves a single batch or all unresolved hints.
- `pipeline:report-relationship-hints` prints actionable counts and samples.
- `PipelineEventHubImportTest` passes and covers late-arriving target retryability.
- All new and existing feature tests pass.
- Docs updated with command examples.
