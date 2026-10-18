<?php

declare(strict_types=1);

namespace App\Actions\ContentBundle;

use App\Support\ContentBundle\BundleFormat;
use App\Support\ContentBundle\BundleWriter;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use App\Support\ContentBundle\Scope\ExportScope;
use App\Support\ContentBundle\Scope\ScopeResolver;
use App\Support\ContentBundle\Serializers\Serializers;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;

/**
 * Exports the rows selected by a scope as a content bundle. The whole export runs in one
 * REPEATABLE READ, READ ONLY transaction so all six files come from the same snapshot and a concurrent
 * edit cannot leave dangling references between them. When the caller already holds a transaction
 * (tests, nested use) the export joins it, because Postgres only allows SET TRANSACTION first.
 * Rows stream by primary key in chunks of 500; no file is ever built in memory.
 */
final class ExportContentBundleAction
{
    private const CHUNK = 500;

    public function __construct(private readonly ScopeResolver $resolver) {}

    /** @return array<string, mixed> the manifest written */
    public function __invoke(string $path, ExportScope $scope, Profile $profile, ?string $source = null): array
    {
        $writer = BundleWriter::open($path);

        try {
            return DB::transaction(function () use ($writer, $scope, $profile, $source) {
                if (DB::transactionLevel() === 1) {
                    DB::statement('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY');
                }

                $builders = $this->resolver->resolve($scope);
                foreach (RecordType::cases() as $type) {
                    $serializer = Serializers::for($type);
                    $table = (new ($type->modelClass()))->getTable();
                    $pk = $type->primaryKey();
                    $rows = $builders[$type->value]->lazyById(self::CHUNK, "{$table}.{$pk}", $pk);

                    $writer->writeRecords($type, (function () use ($rows, $serializer, $profile) {
                        foreach ($rows as $model) {
                            yield $serializer->serialize($model, $profile);
                        }
                    })());
                }

                return $writer->close([
                    'format' => BundleFormat::FORMAT,
                    'version' => BundleFormat::VERSION,
                    'profile' => $profile->value,
                    'exported_at' => CarbonImmutable::now('UTC')->format('Y-m-d\TH:i:s\Z'),
                    'source' => $source ?? (string) config('app.env'),
                    'scope' => $scope->specs(),
                    'base' => 'export',
                ]);
            });
        } catch (\Throwable $e) {
            $writer->abort();
            throw $e;
        }
    }
}
