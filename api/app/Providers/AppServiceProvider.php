<?php

namespace App\Providers;

use App\Ai\ToolRegistry;
use App\Ai\Tools\CreateEntity;
use App\Ai\Tools\CreateRelationship;
use App\Ai\Tools\GetEntityContext;
use App\Ai\Tools\MergeDuplicateEntities;
use App\Ai\Tools\SetEntityLocation;
use App\Ai\Tools\SetEntityWikidata;
use App\Ai\Tools\UpdateEntityFields;
use App\Ai\Tools\VerifyWikidata;
use App\Models\EntityLocation;
use App\Models\EntityRelationship;
use App\Models\EntityTemporalRange;
use App\Models\GeometryPeriod;
use App\Models\User;
use App\Observers\EntityLocationObserver;
use App\Observers\EntityRelationshipObserver;
use App\Observers\EntityTemporalRangeObserver;
use App\Observers\GeometryPeriodObserver;
use Carbon\CarbonImmutable;
use Dedoc\Scramble\Scramble;
use Dedoc\Scramble\Support\Generator\OpenApi;
use Dedoc\Scramble\Support\Generator\SecurityScheme;
use Illuminate\Support\Facades\Date;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\Vite;
use Illuminate\Support\ServiceProvider;
use Illuminate\Validation\Rules\Password;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        $this->app->singleton(ToolRegistry::class);
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        GeometryPeriod::observe(GeometryPeriodObserver::class);
        EntityTemporalRange::observe(EntityTemporalRangeObserver::class);
        EntityRelationship::observe(EntityRelationshipObserver::class);
        EntityLocation::observe(EntityLocationObserver::class);

        app(ToolRegistry::class)->register(CreateEntity::name(), CreateEntity::class);
        app(ToolRegistry::class)->register(CreateRelationship::name(), CreateRelationship::class);
        app(ToolRegistry::class)->register(SetEntityLocation::name(), SetEntityLocation::class);
        app(ToolRegistry::class)->register(UpdateEntityFields::name(), UpdateEntityFields::class);
        app(ToolRegistry::class)->register(GetEntityContext::name(), GetEntityContext::class);
        app(ToolRegistry::class)->register(VerifyWikidata::name(), VerifyWikidata::class);
        app(ToolRegistry::class)->register(SetEntityWikidata::name(), SetEntityWikidata::class);
        app(ToolRegistry::class)->register(MergeDuplicateEntities::name(), MergeDuplicateEntities::class);

        $this->configureDefaults();
        $this->configureAuthorization();
        $this->configureApiDocs();
    }

    /**
     * Authorization defaults.
     *
     * The `admin` role is a super-user: it passes every permission/ability check.
     * All other authorization is permission-based (see PermissionSeeder) and is
     * applied only to write routes — public `/api/v1` GET reads stay open.
     */
    protected function configureAuthorization(): void
    {
        Gate::before(fn (User $user) => $user->hasRole('admin') ? true : null);
    }

    /**
     * Expose the OpenAPI documentation (Scramble) for the public /api/v1 contract.
     *
     * - Local dev: the docs UI (/docs/api) and JSON spec (/docs/api.json) are always open.
     * - Other environments: access requires the `viewApiDocs` gate — granted to the
     *   `admin` role, or to everyone when SCRAMBLE_DOCS_PUBLIC=true.
     * - The Sanctum bearer scheme is documented so write endpoints render as secured.
     */
    protected function configureApiDocs(): void
    {
        Gate::define('viewApiDocs', function (?User $user = null): bool {
            if ((bool) config('scramble.docs_public', false)) {
                return true;
            }

            return $user?->hasRole('admin') ?? false;
        });

        Scramble::extendOpenApi(
            fn (OpenApi $openApi) => $openApi->secure(SecurityScheme::http('bearer')),
        );
    }

    /**
     * Configure default behaviors for production-ready applications.
     */
    protected function configureDefaults(): void
    {
        Date::use(CarbonImmutable::class);

        DB::prohibitDestructiveCommands(
            app()->isProduction(),
        );

        Password::defaults(fn (): ?Password => app()->isProduction()
            ? Password::min(12)
                ->mixedCase()
                ->letters()
                ->numbers()
                ->symbols()
                ->uncompromised()
            : null,
        );

        $this->configureViteFallback();
    }

    /**
     * Keep local Docker dev working when the Vite dev server is up but the
     * standard public/hot marker file is missing on the shared volume.
     */
    protected function configureViteFallback(): void
    {
        if (! app()->isLocal()) {
            return;
        }

        if (is_file(public_path('hot')) || is_file(public_path('build/manifest.json'))) {
            return;
        }

        $devServerUrl = rtrim((string) env('VITE_ADMIN_DEV_SERVER_URL', 'http://localhost:5174'), '/');
        if ($devServerUrl === '') {
            return;
        }

        $hotFile = storage_path('framework/vite.hot');

        Vite::useHotFile($hotFile);

        if (! is_file($hotFile) || trim((string) File::get($hotFile)) !== $devServerUrl) {
            File::ensureDirectoryExists(dirname($hotFile));
            File::put($hotFile, $devServerUrl);
        }
    }
}
