<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/** `{entity}` is a UUID at the router: a malformed id is 404, never a database error. */
class EntityRouteBindingTest extends TestCase
{
    use RefreshDatabase;

    public function test_a_malformed_entity_id_is_not_found(): void
    {
        $this->getJson('/api/v1/entities/not-a-uuid')->assertNotFound();
        $this->getJson('/api/v1/entities/not-a-uuid/relationships')->assertNotFound();
        $this->getJson('/api/v1/entities/not-a-uuid/timeline')->assertNotFound();
    }

    public function test_an_unknown_but_well_formed_id_is_not_found(): void
    {
        $this->getJson('/api/v1/entities/00000000-0000-4000-8000-000000000000')->assertNotFound();
    }
}
