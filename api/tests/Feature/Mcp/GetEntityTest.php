<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

use App\Actions\Tag\SyncTagsAction;
use App\Enums\EntityType;
use App\Enums\TagSource;
use App\Mcp\Servers\AtlasServer;
use App\Mcp\Tools\GetEntity;
use App\Models\Entity;
use App\Models\EntityAlias;

class GetEntityTest extends McpTestCase
{
    private function napoleon(): Entity
    {
        $e = $this->placed('Napoleon Testus', 9.1, 41.9, 1769, 1821, [
            'entity_type' => EntityType::Person->value,
            'wikidata_id' => 'Q517',
            'description' => 'He crowned himself.',
            'attributes' => ['media_refs' => [[
                'type' => 'image',
                'url' => 'https://thumb.example/n.jpg',
                'original_url' => 'https://upload.example/n.jpg',
                'page_url' => 'https://commons.example/File:N.jpg',
                'author' => 'J.-L. David',
                'license' => 'Public domain',
            ]]],
        ]);
        EntityAlias::query()->create(['entity_id' => $e->entity_id, 'name' => 'Bonaparte']);
        app(SyncTagsAction::class)($e, ['Empire'], TagSource::Manual);

        return $e;
    }

    public function test_by_id_returns_the_full_record(): void
    {
        $e = $this->napoleon();
        $son = $this->entity('Napoleon II', EntityType::Person, ['impact_score' => 50]);
        $battle = $this->entity('Battle of Testing', EntityType::EventBattle, ['impact_score' => 90]);
        $this->relate($e, $son, 'parent_of');
        $this->relate($battle, $e, 'participated_in');
        $this->chronicle('The Napoleonic Tale');

        AtlasServer::tool(GetEntity::class, ['id' => $e->entity_id])
            ->assertOk()
            ->assertStructuredContentPath('entity.id', $e->entity_id)
            ->assertStructuredContentPath('entity.date_label', '1769–1821')
            ->assertStructuredContentPath('entity.aliases', ['Bonaparte'])
            ->assertStructuredContentPath('entity.description', 'He crowned himself.')
            ->assertStructuredContentPath('entity.wikidata_qid', 'Q517')
            ->assertStructuredContentPath('entity.wikipedia_url', 'https://www.wikidata.org/wiki/Special:GoToLinkedPage/enwiki/Q517')
            ->assertStructuredContentPath('entity.tags', ['empire'])
            ->assertStructuredContentPath('entity.locations.0', ['name' => 'Napoleon Testus place', 'lng' => 9.1, 'lat' => 41.9, 'is_primary' => true])
            ->assertStructuredContentPath('entity.image', [
                'url' => 'https://upload.example/n.jpg',
                'thumb_url' => 'https://thumb.example/n.jpg',
                'credit' => 'J.-L. David',
                'license' => 'Public domain',
                'source_url' => 'https://commons.example/File:N.jpg',
            ])
            ->assertStructuredContentPath('entity.image_url', 'https://thumb.example/n.jpg')
            ->assertStructuredContentCount(2, 'entity.relationships')
            // Most important neighbour first.
            ->assertStructuredContentPath('entity.relationships.0.label', 'had participant')
            ->assertStructuredContentPath('entity.relationships.0.direction', 'in')
            ->assertStructuredContentPath('entity.relationships.0.other.name', 'Battle of Testing')
            ->assertStructuredContentPath('entity.relationships.1.label', 'parent of')
            ->assertStructuredContentPath('entity.relationships.1.direction', 'out')
            ->assertStructuredContentPath('entity.relationships.1.other.type', 'person')
            ->assertStructuredContentPath('entity.relationships.1.other.atlas_url', 'https://atlas.test/entities/'.$son->entity_id);
    }

    public function test_by_qid_and_by_name(): void
    {
        $e = $this->napoleon();

        AtlasServer::tool(GetEntity::class, ['qid' => 'q517'])->assertStructuredContentPath('entity.id', $e->entity_id);
        AtlasServer::tool(GetEntity::class, ['name' => 'napoleon testus'])->assertStructuredContentPath('entity.id', $e->entity_id);
        // No exact name: the top search hit.
        AtlasServer::tool(GetEntity::class, ['name' => 'Napoleon Testu'])->assertStructuredContentPath('entity.id', $e->entity_id);
    }

    public function test_an_exact_name_beats_a_more_important_partial_match(): void
    {
        $exact = $this->entity('Rome', null, ['impact_score' => 5]);
        $this->entity('Rome Total War', null, ['impact_score' => 99]);

        AtlasServer::tool(GetEntity::class, ['name' => 'rome'])->assertStructuredContentPath('entity.id', $exact->entity_id);
    }

    public function test_entity_without_image_or_place_has_nulls_and_empty_lists(): void
    {
        $e = $this->entity('Bare Entity');

        AtlasServer::tool(GetEntity::class, ['id' => $e->entity_id])
            ->assertOk()
            ->assertStructuredContentPath('entity.image', null)
            ->assertStructuredContentPath('entity.image_url', null)
            ->assertStructuredContentPath('entity.lng', null)
            ->assertStructuredContentPath('entity.wikipedia_url', null)
            ->assertStructuredContentPath('entity.locations', [])
            ->assertStructuredContentPath('entity.relationships', [])
            ->assertStructuredContentPath('entity.chronicles', []);
    }

    public function test_relationships_are_capped_at_twelve(): void
    {
        $hub = $this->entity('Hub');
        foreach (range(1, 15) as $i) {
            $this->relate($hub, $this->entity("Spoke {$i}"));
        }

        AtlasServer::tool(GetEntity::class, ['id' => $hub->entity_id])
            ->assertStructuredContentCount(12, 'entity.relationships');
    }

    public function test_chronicles_the_entity_appears_in_exclude_archived_ones(): void
    {
        $e = $this->entity('In A Story');
        $shown = $this->chronicle('Shown Story');
        $hidden = $this->chronicle('Hidden Story', [], ['status' => 'archived']);
        $this->entry($shown, 1, 'It happened.', [$e]);
        $this->entry($hidden, 1, 'It happened.', [$e]);

        AtlasServer::tool(GetEntity::class, ['id' => $e->entity_id])
            ->assertStructuredContentCount(1, 'entity.chronicles')
            ->assertStructuredContentPath('entity.chronicles.0.slug', 'shown-story');
    }

    public function test_unknown_ids_return_a_helpful_error(): void
    {
        AtlasServer::tool(GetEntity::class, ['id' => '00000000-0000-4000-8000-000000000000'])
            ->assertHasErrors(['search_atlas']);
        AtlasServer::tool(GetEntity::class, ['qid' => 'Q999999999'])->assertHasErrors(['Q999999999']);
        AtlasServer::tool(GetEntity::class, ['name' => 'Zzzyzxx Nonexistent'])->assertHasErrors(['search_atlas']);
    }

    public function test_validation_errors(): void
    {
        AtlasServer::tool(GetEntity::class, [])->assertHasErrors(['Give one of id, qid or name.']);
        AtlasServer::tool(GetEntity::class, ['id' => 'not-a-uuid'])->assertHasErrors();
        AtlasServer::tool(GetEntity::class, ['qid' => 'Napoleon'])->assertHasErrors();
    }
}
