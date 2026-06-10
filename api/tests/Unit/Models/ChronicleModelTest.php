<?php

declare(strict_types=1);

namespace Tests\Unit\Models;

use App\Models\Chronicle;
use PHPUnit\Framework\TestCase;

class ChronicleModelTest extends TestCase
{
    public function test_chronicle_has_expected_fillable(): void
    {
        $chronicle = new Chronicle();
        $this->assertContains('title', $chronicle->getFillable());
        $this->assertContains('slug', $chronicle->getFillable());
        $this->assertContains('status', $chronicle->getFillable());
    }

    public function test_chronicle_casts(): void
    {
        $chronicle = new Chronicle();
        $casts = $chronicle->getCasts();
        $this->assertArrayHasKey('status', $casts);
        $this->assertArrayHasKey('source_type', $casts);
        $this->assertArrayHasKey('metadata', $casts);
    }
}
