<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

class DashboardTest extends TestCase
{
    use RefreshDatabase;

    public function test_guests_are_redirected_to_the_login_page(): void
    {
        $response = $this->get(route('dashboard'));
        $response->assertRedirect(route('login'));
    }

    public function test_staff_can_visit_the_dashboard(): void
    {
        $this->actingAs($this->userWithPermissions(['admin.access']));

        $response = $this->get(route('dashboard'));
        $response->assertOk();
        $response->assertInertia(fn (Assert $page) => $page->component('dashboard'));
    }

    public function test_registered_users_without_admin_access_are_forbidden(): void
    {
        $this->actingAs($this->userWithRole('user'));

        $this->get(route('dashboard'))->assertForbidden();
        $this->get(route('entities.index'))->assertForbidden();
        $this->get(route('chronicles.index'))->assertForbidden();
    }

    public function test_settings_stay_open_to_registered_users(): void
    {
        $this->actingAs($this->userWithRole('user'));

        $this->get(route('profile.edit'))->assertOk();
    }
}
