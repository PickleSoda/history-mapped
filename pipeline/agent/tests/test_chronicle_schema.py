from pipeline.agent.schemas.chronicle import Chronicle, ChronicleEntry, ChronicleEntryEntity


def test_chronicle_schema():
    c = Chronicle(
        title="Alexander the Great",
        slug="alexander-the-great",
        source_type="video_transcript",
        source_reference="transcript.txt",
        entries=[],
    )
    assert c.title == "Alexander the Great"
    assert c.status == "draft"


def test_chronicle_entry_schema():
    e = ChronicleEntry(
        sequence_order=1,
        narrative_text="Alexander crossed the Hellespont.",
        primary_relationship_id="rel-123",
        secondary_entities=[ChronicleEntryEntity(entity_id="ent-456", role="participant")],
    )
    assert e.sequence_order == 1
    assert len(e.secondary_entities) == 1
