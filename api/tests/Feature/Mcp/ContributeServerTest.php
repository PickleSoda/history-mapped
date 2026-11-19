<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

use App\Mcp\Servers\AtlasServer;
use App\Mcp\Servers\ContributeServer;
use App\Mcp\Tools\Contribute\MyContributions;
use App\Mcp\Tools\Contribute\ProposeEntity;
use App\Mcp\Tools\Contribute\ProposeRelationship;
use App\Mcp\Tools\Contribute\SuggestCorrection;
use App\Models\User;
use Laravel\Passport\Client;
use Laravel\Passport\ClientRepository;
use Laravel\Passport\Passport;

/** /mcp/contribute: OAuth protection, discovery, and who sees which tools. */
class ContributeServerTest extends ContributeTestCase
{
    private const READ = ['search-atlas', 'get-entity', 'what-was-happening', 'get-connections', 'find-chronicles', 'get-chronicle'];

    private const WRITE = ['suggest-correction', 'propose-entity', 'propose-relationship', 'my-contributions'];

    private const HEADERS = ['Accept' => 'application/json, text/event-stream'];

    /** @return list<string> */
    private function listedOverHttp(?User $user): array
    {
        if ($user !== null) {
            Passport::actingAs($user, ['mcp:use']);
        }

        return collect($this->postJson('/mcp/contribute', ['jsonrpc' => '2.0', 'id' => 1, 'method' => 'tools/list'], self::HEADERS)
            ->assertOk()->json('result.tools'))->pluck('name')->all();
    }

    public function test_unauthenticated_requests_get_401_with_the_resource_metadata_challenge(): void
    {
        $response = $this->postJson('/mcp/contribute', ['jsonrpc' => '2.0', 'id' => 1, 'method' => 'tools/list'], self::HEADERS);

        $response->assertUnauthorized();
        $challenge = (string) $response->headers->get('WWW-Authenticate');
        $this->assertStringContainsString('Bearer', $challenge);
        $this->assertStringContainsString('resource_metadata="'.url('/.well-known/oauth-protected-resource/mcp/contribute').'"', $challenge);
    }

    public function test_a_garbage_bearer_token_is_rejected(): void
    {
        $this->postJson('/mcp/contribute', ['jsonrpc' => '2.0', 'id' => 1, 'method' => 'tools/list'], self::HEADERS + ['Authorization' => 'Bearer nope'])
            ->assertUnauthorized();
    }

    public function test_oauth_discovery_endpoints_respond(): void
    {
        $resource = $this->getJson('/.well-known/oauth-protected-resource/mcp/contribute')->assertOk();
        $resource->assertJsonPath('resource', url('/mcp/contribute'));
        $resource->assertJsonPath('authorization_servers.0', url('/'));

        $server = $this->getJson('/.well-known/oauth-authorization-server')->assertOk();
        $server->assertJsonPath('authorization_endpoint', url('/oauth/authorize'))
            ->assertJsonPath('token_endpoint', url('/oauth/token'))
            ->assertJsonPath('registration_endpoint', url('/oauth/register'))
            ->assertJsonPath('code_challenge_methods_supported.0', 'S256');
    }

    public function test_claude_can_register_a_client_and_other_redirects_are_refused(): void
    {
        foreach (['https://claude.ai/api/mcp/auth_callback', 'https://claude.com/api/mcp/auth_callback'] as $uri) {
            $this->postJson('/oauth/register', ['client_name' => 'Claude', 'redirect_uris' => [$uri]])
                ->assertCreated()
                ->assertJsonPath('redirect_uris.0', $uri)
                ->assertJsonPath('token_endpoint_auth_method', 'none');
        }
        $this->assertSame(2, Client::query()->where('name', 'Claude')->count());

        $this->postJson('/oauth/register', ['client_name' => 'Evil', 'redirect_uris' => ['https://evil.example/cb']])
            ->assertStatus(400)->assertJsonPath('error', 'invalid_redirect_uri');
        $this->postJson('/oauth/register', ['client_name' => 'Evil', 'redirect_uris' => ['claude-evil://cb/x']])
            ->assertStatus(400);
        $this->assertSame(0, Client::query()->where('name', 'Evil')->count());
    }

    public function test_the_authorize_page_requires_the_web_sign_in(): void
    {
        $client = app(ClientRepository::class)->createAuthorizationCodeGrantClient(
            'Claude', ['https://claude.ai/api/mcp/auth_callback'], confidential: false,
        );
        $query = http_build_query([
            'client_id' => $client->getKey(), 'redirect_uri' => 'https://claude.ai/api/mcp/auth_callback',
            'response_type' => 'code', 'scope' => 'mcp:use', 'state' => 'x',
            'code_challenge' => str_repeat('a', 43), 'code_challenge_method' => 'S256',
        ]);

        // Signed out: sent to the normal sign-in page.
        $this->get('/oauth/authorize?'.$query)->assertRedirect('/login');
    }

    public function test_signing_in_from_the_consent_page_returns_to_the_authorize_url_for_any_role(): void
    {
        $client = app(ClientRepository::class)->createAuthorizationCodeGrantClient(
            'Claude', ['https://claude.ai/api/mcp/auth_callback'], confidential: false,
        );
        $authorize = '/oauth/authorize?'.http_build_query([
            'client_id' => $client->getKey(), 'redirect_uri' => 'https://claude.ai/api/mcp/auth_callback',
            'response_type' => 'code', 'scope' => 'mcp:use', 'state' => 'x',
            'code_challenge' => str_repeat('a', 43), 'code_challenge_method' => 'S256',
        ]);
        $user = $this->userWithRole('user'); // no admin.access: normally sent to the public site

        $this->get($authorize)->assertRedirect('/login');
        $back = (string) $this->post('/login', ['email' => $user->email, 'password' => 'password'])->assertRedirect()->headers->get('Location');
        $this->assertStringStartsWith(url('/oauth/authorize?'), $back);
        $this->assertStringContainsString('client_id='.$client->getKey(), $back);
        // The sign-in carried on to the consent page.
        $this->get($authorize)->assertOk()->assertSee('Authorize Claude');
    }

    public function test_a_plain_sign_in_still_sends_non_staff_to_the_public_site(): void
    {
        $user = $this->userWithRole('user');

        $this->post('/login', ['email' => $user->email, 'password' => 'password'])
            ->assertRedirect(config('app.frontend_url').'/');
    }

    public function test_a_contributor_sees_the_read_tools_and_the_contribution_tools(): void
    {
        $names = $this->listedOverHttp($this->userWithRole('user'));

        $this->assertEqualsCanonicalizing([...self::READ, ...self::WRITE], $names);
    }

    public function test_an_account_without_the_permission_sees_only_the_read_tools(): void
    {
        $this->seedRbac();

        $this->assertEqualsCanonicalizing(self::READ, $this->listedOverHttp(User::factory()->create()));
    }

    public function test_the_write_tools_are_not_read_only(): void
    {
        Passport::actingAs($this->userWithRole('user'), ['mcp:use']);
        $tools = collect($this->postJson('/mcp/contribute', ['jsonrpc' => '2.0', 'id' => 1, 'method' => 'tools/list'], self::HEADERS)
            ->assertOk()->json('result.tools'))->keyBy('name');

        foreach (self::WRITE as $name) {
            $this->assertFalse($tools[$name]['annotations']['readOnlyHint'], $name);
            $this->assertNotEmpty($tools[$name]['inputSchema']['properties'], $name);
        }
        foreach (self::READ as $name) {
            $this->assertTrue($tools[$name]['annotations']['readOnlyHint'], $name);
        }
    }

    public function test_a_hidden_tool_cannot_be_called_without_the_permission(): void
    {
        $this->seedRbac();
        $user = User::factory()->create();

        ContributeServer::actingAs($user)->tool(ProposeEntity::class, ['name' => 'Nowhere', 'entity_type' => 'city'])
            ->assertHasErrors();
        $this->assertSame(0, $user->contributions()->count());
    }

    public function test_the_tools_are_hidden_from_a_guest_test_user(): void
    {
        foreach ([SuggestCorrection::class, ProposeEntity::class, ProposeRelationship::class, MyContributions::class] as $tool) {
            ContributeServer::tool($tool, [])->assertHasErrors();
        }
    }

    public function test_read_tools_work_on_the_contributor_server_over_http(): void
    {
        $this->placed('Httpia', 10, 40, 1400, 1600);
        Passport::actingAs($this->userWithRole('user'), ['mcp:use']);

        $this->postJson('/mcp/contribute', [
            'jsonrpc' => '2.0', 'id' => 2, 'method' => 'tools/call',
            'params' => ['name' => 'search-atlas', 'arguments' => ['query' => 'Httpia']],
        ], self::HEADERS)
            ->assertOk()
            ->assertJsonPath('result.structuredContent.entities.0.name', 'Httpia');
    }

    public function test_the_public_server_is_unchanged_and_has_no_contribution_tools(): void
    {
        // No sign-in, and not even an authenticated contributor reaches the write tools on /mcp.
        $names = collect($this->postJson('/mcp', ['jsonrpc' => '2.0', 'id' => 1, 'method' => 'tools/list'], self::HEADERS)
            ->assertOk()->json('result.tools'))->pluck('name')->all();
        $this->assertEqualsCanonicalizing(self::READ, $names);

        Passport::actingAs($this->userWithRole('user'), ['mcp:use']);
        $names = collect($this->postJson('/mcp', ['jsonrpc' => '2.0', 'id' => 1, 'method' => 'tools/list'], self::HEADERS)
            ->assertOk()->json('result.tools'))->pluck('name')->all();
        $this->assertEqualsCanonicalizing(self::READ, $names);

        AtlasServer::tool(ProposeEntity::class, ['name' => 'X', 'entity_type' => 'city'])->assertHasErrors();
    }
}
