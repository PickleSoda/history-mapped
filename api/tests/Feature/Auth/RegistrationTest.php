<?php

namespace Tests\Feature\Auth;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Fortify\Features;
use Tests\TestCase;

class RegistrationTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        $this->skipUnlessFortifyFeature(Features::registration());
    }

    public function test_registration_screen_can_be_rendered()
    {
        $response = $this->get(route('register'));

        $response->assertOk();
    }

    public function test_new_users_can_register()
    {
        $response = $this->post(route('register.store'), [
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => 'password',
            'password_confirmation' => 'password',
        ]);

        $this->assertAuthenticated();
        // A fresh account is not staff, so it lands on the public atlas.
        $response->assertRedirect(config('app.frontend_url').'/');
    }

    public function test_new_users_get_the_default_user_role()
    {
        $this->postJson(route('register.store'), [
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => 'password',
            'password_confirmation' => 'password',
        ])->assertCreated();

        $user = User::where('email', 'test@example.com')->firstOrFail();
        $this->assertSame(['user'], $user->getRoleNames()->all());
        $this->assertTrue($user->can('contributions.create'));
        $this->assertFalse($user->can('admin.access'));
        $this->assertFalse($user->can('contributions.review'));
    }
}
