<?php

declare(strict_types=1);

namespace App\DTOs;

use App\Enums\ReliabilityTier;

/**
 * Data Transfer Object for creating a Source.
 */
readonly class SourceData
{
    public function __construct(
        public string $title,
        public ReliabilityTier $sourceType,
        public ?string $documentType = null,
        public ?string $author = null,
        public ?string $dateCreated = null,
        public ?string $dateDiscovered = null,
        public ?string $language = null,
        public ?string $currentLocation = null,
        public ?string $sourceUrl = null,
        public ?string $contentHash = null,
        public ?string $geographicScope = null,
        public ?string $temporalScope = null,
        public ?string $contemporaneity = null,
        public ?string $authorBias = null,
        public ?string $corroboration = null,
        public ?string $scholarlyConsensus = null,
    ) {}

    /**
     * Create from validated request data.
     *
     * @param  array<string, mixed>  $validated
     */
    public static function fromArray(array $validated): self
    {
        return new self(
            title: $validated['title'],
            sourceType: ReliabilityTier::from($validated['source_type']),
            documentType: $validated['document_type'] ?? null,
            author: $validated['author'] ?? null,
            dateCreated: $validated['date_created'] ?? null,
            dateDiscovered: $validated['date_discovered'] ?? null,
            language: $validated['language'] ?? null,
            currentLocation: $validated['current_location'] ?? null,
            sourceUrl: $validated['source_url'] ?? null,
            contentHash: $validated['content_hash'] ?? null,
            geographicScope: $validated['geographic_scope'] ?? null,
            temporalScope: $validated['temporal_scope'] ?? null,
            contemporaneity: $validated['contemporaneity'] ?? null,
            authorBias: $validated['author_bias'] ?? null,
            corroboration: $validated['corroboration'] ?? null,
            scholarlyConsensus: $validated['scholarly_consensus'] ?? null,
        );
    }

    /**
     * @return array<string, mixed>
     */
    public function toModelArray(): array
    {
        $data = [
            'title' => $this->title,
            'source_type' => $this->sourceType->value,
        ];

        $optionals = [
            'document_type' => $this->documentType,
            'author' => $this->author,
            'date_created' => $this->dateCreated,
            'date_discovered' => $this->dateDiscovered,
            'language' => $this->language,
            'current_location' => $this->currentLocation,
            'source_url' => $this->sourceUrl,
            'content_hash' => $this->contentHash,
            'geographic_scope' => $this->geographicScope,
            'temporal_scope' => $this->temporalScope,
            'contemporaneity' => $this->contemporaneity,
            'author_bias' => $this->authorBias,
            'corroboration' => $this->corroboration,
            'scholarly_consensus' => $this->scholarlyConsensus,
        ];

        foreach ($optionals as $key => $value) {
            if ($value !== null) {
                $data[$key] = $value;
            }
        }

        return $data;
    }
}
