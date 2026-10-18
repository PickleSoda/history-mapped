<?php

use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Schedule;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Schedule::command('ai:prune-proposals')->daily();

// Images for entities that got a Wikidata id outside `pipeline:import`
// (repair passes, admin edits). Only unchecked entities are fetched.
Schedule::command('entity:fetch-images --limit=2000')->dailyAt('03:30')->withoutOverlapping();
