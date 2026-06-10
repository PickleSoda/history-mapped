<?php

declare(strict_types=1);

namespace Tests\Unit\Enums;

use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use App\Enums\ChronicleEntryRole;
use PHPUnit\Framework\TestCase;

class ChronicleEnumsTest extends TestCase
{
    public function test_chronicle_status_values(): void
    {
        $this->assertSame('draft', ChronicleStatus::Draft->value);
        $this->assertSame('published', ChronicleStatus::Published->value);
        $this->assertSame('archived', ChronicleStatus::Archived->value);
    }

    public function test_source_type_values(): void
    {
        $this->assertSame('video_transcript', SourceType::VideoTranscript->value);
        $this->assertSame('article', SourceType::Article->value);
        $this->assertSame('book_excerpt', SourceType::BookExcerpt->value);
        $this->assertSame('manual', SourceType::Manual->value);
    }

    public function test_entry_role_values(): void
    {
        $this->assertSame('participant', ChronicleEntryRole::Participant->value);
        $this->assertSame('mentioned', ChronicleEntryRole::Mentioned->value);
        $this->assertSame('location', ChronicleEntryRole::Location->value);
        $this->assertSame('outcome', ChronicleEntryRole::Outcome->value);
    }
}
