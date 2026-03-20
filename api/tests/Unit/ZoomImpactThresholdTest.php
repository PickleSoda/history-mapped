<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\ZoomImpactThreshold;
use PHPUnit\Framework\TestCase;

class ZoomImpactThresholdTest extends TestCase
{
    public function test_zoom_0_returns_80(): void
    {
        $this->assertSame(80, ZoomImpactThreshold::forZoom(0));
    }

    public function test_zoom_2_returns_80(): void
    {
        $this->assertSame(80, ZoomImpactThreshold::forZoom(2));
    }

    public function test_zoom_3_returns_60(): void
    {
        $this->assertSame(60, ZoomImpactThreshold::forZoom(3));
    }

    public function test_zoom_5_returns_60(): void
    {
        $this->assertSame(60, ZoomImpactThreshold::forZoom(5));
    }

    public function test_zoom_6_returns_40(): void
    {
        $this->assertSame(40, ZoomImpactThreshold::forZoom(6));
    }

    public function test_zoom_8_returns_40(): void
    {
        $this->assertSame(40, ZoomImpactThreshold::forZoom(8));
    }

    public function test_zoom_9_returns_20(): void
    {
        $this->assertSame(20, ZoomImpactThreshold::forZoom(9));
    }

    public function test_zoom_11_returns_20(): void
    {
        $this->assertSame(20, ZoomImpactThreshold::forZoom(11));
    }

    public function test_zoom_12_returns_null(): void
    {
        $this->assertNull(ZoomImpactThreshold::forZoom(12));
    }

    public function test_zoom_22_returns_null(): void
    {
        $this->assertNull(ZoomImpactThreshold::forZoom(22));
    }
}
