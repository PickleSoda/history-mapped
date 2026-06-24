<?php

declare(strict_types=1);

namespace App\DTOs;

readonly class ChronicleEntryData
{
    /** @param list<string>|null $entityIds */
    public function __construct(
        public ?string $narrativeText = null,
        public ?string $notes = null,
        public ?array $entityIds = null,
        public ?string $primaryRelationshipId = null,
    ) {}
}
