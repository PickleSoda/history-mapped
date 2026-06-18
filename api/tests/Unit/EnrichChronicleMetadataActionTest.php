<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Actions\Chronicle\EnrichChronicleMetadataAction;
use PHPUnit\Framework\TestCase;

class EnrichChronicleMetadataActionTest extends TestCase
{
    public function test_null_peak_returns_null(): void
    {
        $this->assertNull(EnrichChronicleMetadataAction::computeChronicleImpact(null, 50.0));
    }

    public function test_mean_separates_dense_from_shallow_chronicles(): void
    {
        // Same peak (98); one chronicle is dense with major entities (high mean),
        // the other name-drops one empire among minor figures (low mean).
        $dense = EnrichChronicleMetadataAction::computeChronicleImpact(98, 90.0);
        $shallow = EnrichChronicleMetadataAction::computeChronicleImpact(98, 55.0);

        $this->assertGreaterThan($shallow, $dense, 'A denser chronicle should outrank a shallow one with the same peak');
        // 0.7*98 + 0.3*90 = 95.6 → 96 ; 0.7*98 + 0.3*55 = 85.1 → 85
        $this->assertSame(96, $dense);
        $this->assertSame(85, $shallow);
    }

    public function test_blend_stays_in_range_and_handles_missing_mean(): void
    {
        // Null mean falls back to peak → score equals peak.
        $this->assertSame(50, EnrichChronicleMetadataAction::computeChronicleImpact(50, null));
        // Blend never exceeds 100 or drops below 1.
        $this->assertLessThanOrEqual(100, EnrichChronicleMetadataAction::computeChronicleImpact(100, 100.0));
        $this->assertGreaterThanOrEqual(1, EnrichChronicleMetadataAction::computeChronicleImpact(1, 1.0));
    }
}
