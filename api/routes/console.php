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

// Atlas tiles are cut from a precomputed table; this refreshes it only when
// the content changed since the last run (tiles.change_seq moved).
Schedule::command('tiles:refresh')->everyFiveMinutes()->withoutOverlapping();

// "On this day" reads a small table of the dates that have a real day. The
// rebuild reads every person's attributes once (tens of seconds on the
// droplet), so it runs weekly, at a quiet hour. A first deploy or a content
// load leaves the table empty: the hourly run builds it then, and is one
// cheap query otherwise.
Schedule::command('discover:build-anniversaries')->weeklyOn(1, '04:10')->withoutOverlapping();
Schedule::command('discover:build-anniversaries --if-empty')->hourlyAt(20)->withoutOverlapping();
