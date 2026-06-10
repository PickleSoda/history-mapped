<?php

declare(strict_types=1);

namespace Tests\Unit\Models;

use App\Models\ChronicleEntry;
use PHPUnit\Framework\TestCase;

class ChronicleEntryModelTest extends TestCase
{
    public function test_entry_has_expected_relationship_methods(): void
    {
        $entry = new ChronicleEntry();
        $this->assertTrue(method_exists($entry, 'chronicle'));
        $this->assertTrue(method_exists($entry, 'primaryRelationship'));
        $this->assertTrue(method_exists($entry, 'secondaryEntities'));
    }
}
