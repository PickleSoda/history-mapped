<?php

namespace App\Providers;

use App\Models\EntityLocation;
use App\Models\EntityRelationship;
use App\Models\EntityTemporalRange;
use App\Models\GeometryPeriod;
use App\Observers\EntityLocationObserver;
use App\Observers\EntityRelationshipObserver;
use App\Observers\EntityTemporalRangeObserver;
use App\Observers\GeometryPeriodObserver;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Date;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
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
        //
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

        $this->configureDefaults();
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
