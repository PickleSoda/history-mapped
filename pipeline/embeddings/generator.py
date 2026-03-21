"""Standalone embedding generator.

Can be used Python-side to pre-compute embeddings before import,
or the embeddings can be generated on the Laravel side after import
via the pipeline:embeddings artisan command.

The Laravel-side approach is recommended for production because:
1. Embeddings are regenerated when entities are updated
2. Laravel controls the embedding_version column
3. Keeps the source of truth in one system

The Python-side approach is useful for:
1. Batch embedding of large datasets before import
2. Testing embedding quality before committing to DB
3. Running on a GPU machine separate from the web server
"""

from __future__ import annotations

import logging
from typing import Any

from pipeline.config import settings

logger = logging.getLogger(__name__)


def build_embedding_text(entity: dict[str, Any]) -> str:
    """Build the text to embed for a given entity.

    Combines structured fields into a single text passage optimized
    for semantic similarity search. This exact format should be
    mirrored in the Laravel GenerateEntityEmbeddingJob.

    The text is structured as:
        [entity_type] Name (alternative names)
        Summary text...
        Significance text...
        Tags: tag1, tag2
        Temporal: start — end
        Location: location_name
    """
    parts = []

    # Type + Name header
    etype = entity.get("entity_type", "entity")
    name = entity.get("name", "")
    alt_names = entity.get("alternative_names", [])
    header = f"[{etype}] {name}"
    if alt_names:
        header += f" ({', '.join(alt_names[:5])})"
    parts.append(header)

    # Summary
    summary = entity.get("summary")
    if summary:
        parts.append(summary)

    # Significance
    significance = entity.get("significance")
    if significance:
        parts.append(significance)

    # Tags
    tags = entity.get("tags", [])
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    # Temporal range
    t_start = entity.get("temporal_start")
    t_end = entity.get("temporal_end")
    if t_start or t_end:
        temporal = f"Temporal: {t_start or '?'} — {t_end or '?'}"
        parts.append(temporal)

    # Location
    location = entity.get("location_name")
    if location:
        parts.append(f"Location: {location}")

    return "\n".join(parts)


class EmbeddingGenerator:
    """Generate embeddings using OpenAI's API."""

    def __init__(self, model: str | None = None):
        self.model = model or settings.openai_embedding_model

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set — cannot generate embeddings")

        from openai import OpenAI
        self.client = OpenAI(api_key=settings.openai_api_key)

    def embed_batch(
        self,
        entities: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Add embedding vectors to a list of entity dicts.

        Modifies entities in-place, adding:
        - embedding: list[float] (1536 dimensions for text-embedding-3-small)
        - embedding_version: model identifier string
        """
        for i in range(0, len(entities), batch_size):
            batch = entities[i : i + batch_size]
            texts = [build_embedding_text(e) for e in batch]

            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                )

                for j, embedding_data in enumerate(response.data):
                    batch[j]["embedding"] = embedding_data.embedding
                    batch[j]["embedding_version"] = self.model

                logger.info(f"Embedded batch {i // batch_size + 1} ({len(batch)} entities)")

            except Exception as e:
                logger.error(f"Embedding batch failed: {e}")
                # Don't add embeddings to failed entities — they'll be picked
                # up by the Laravel-side embedding job later

        return entities

    def embed_single(self, entity: dict[str, Any]) -> list[float] | None:
        """Embed a single entity. Returns the vector or None on failure."""
        text = build_embedding_text(entity)
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=[text],
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding failed for {entity.get('name')}: {e}")
            return None
