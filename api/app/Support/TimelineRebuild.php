<?php

declare(strict_types=1);

namespace App\Support;

use App\Jobs\RebuildEntityTimelineJob;

/**
 * Central dispatch point for entity-timeline rebuilds.
 *
 * Model observers route through here instead of dispatching
 * {@see RebuildEntityTimelineJob} directly, so a bulk import can wrap its
 * work in {@see self::withoutRebuilds()} and collapse what would otherwise be
 * a storm of per-row jobs into exactly one rebuild per affected entity.
 */
class TimelineRebuild
{
    private static bool $suppressed = false;

    /** @var array<string, true> Entity ids queued while suppressed. */
    private static array $pending = [];

    /**
     * Queue a rebuild for an entity, or collect it for a batch flush when
     * rebuilds are currently suppressed.
     */
    public static function queue(string $entityId): void
    {
        if ($entityId === '') {
            return;
        }

        if (self::$suppressed) {
            self::$pending[$entityId] = true;

            return;
        }

        RebuildEntityTimelineJob::dispatch($entityId);
    }

    /**
     * Run $callback with per-entity rebuilds suppressed, then dispatch exactly
     * one rebuild per affected entity. Nesting is safe — only the outermost
     * call flushes.
     *
     * @template T
     *
     * @param  callable(): T  $callback
     * @return T
     */
    public static function withoutRebuilds(callable $callback): mixed
    {
        $wasSuppressed = self::$suppressed;
        self::$suppressed = true;

        try {
            return $callback();
        } finally {
            self::$suppressed = $wasSuppressed;

            if (! $wasSuppressed) {
                $pending = array_keys(self::$pending);
                self::$pending = [];

                foreach ($pending as $entityId) {
                    RebuildEntityTimelineJob::dispatch($entityId);
                }
            }
        }
    }
}
