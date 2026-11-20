<?php

declare(strict_types=1);

/*
|--------------------------------------------------------------------------
| Discover: "Today" on the browse page and in the atlas (spec 2026-11-20)
|--------------------------------------------------------------------------
|
| Four public endpoints under /api/v1/discover: on this day, meanwhile in a
| year, the daily expedition and suggestions from what a browser opened.
| Contract: docs/schemas/rest-api.md ("Discover"). Everything tunable lives
| here; `.env` keys are named in each comment.
|
*/

return [

    // The day of expedition 1 (DISCOVER_QUEST_EPOCH, YYYY-MM-DD, a UTC day).
    // Changing it renumbers every expedition.
    'quest_epoch' => env('DISCOVER_QUEST_EPOCH', '2026-11-20'),

    'on_this_day' => [
        // Items in an answer.
        'size' => 8,
        // People (born / died) among them, at most.
        'max_people' => 4,
        // Other kinds among them, at least, when the day has that many.
        'min_others' => 2,
        // A day with fewer items than this borrows from its neighbours,
        // one day further each time, up to `max_widen` days either side.
        'min_items' => 4,
        'max_widen' => 3,
    ],

    'anniversaries' => [
        // People's birth and death dates are read from `attributes` only at
        // or above this impact score (35,000 of 310,000 day-dated people).
        'people_min_impact' => 60,
        // A date known only to the month is stored as the 1st of that month,
        // so many things "founded on the 1st" were not. What to do with a
        // date on a 1st (DISCOVER_FIRST_OF_MONTH): `stated` keeps it only
        // when the entity's summary gives that day, `all` keeps them, `none`
        // drops them. 1 January is always left out: it stands for a date
        // known only to the year.
        'first_of_month' => env('DISCOVER_FIRST_OF_MONTH', 'stated'),
    ],

    'meanwhile' => [
        // An event counts when it falls within this many years of the year:
        // the same window the tiles keep an event on the map.
        'window' => 10,
        // The earliest year that can be asked for; the latest is this year.
        'min_year' => -4000,
    ],

    'quest' => [
        // Battles shown from this zoom or lower (importance 80 and up).
        'max_zoom' => 3,
        // A target needs a clue: a summary of at least this many characters.
        'min_summary' => 40,
        // "easy": a battle map, or at least this many chronicle mentions.
        // "hard": never mentioned. "medium": the rest. Measured 2026-11-20 on
        // the pool of 1,959 battles: 309 easy, 1,271 medium, 379 hard.
        'easy_min_mentions' => 2,
        // `date` may be this many days from the server's UTC day.
        'date_tolerance_days' => 2,
    ],

    'for_you' => [
        // Recently opened entities a request may send.
        'max_ids' => 12,
        // Relationships read per seed, half outgoing and half incoming.
        'walk' => 400,
        // Suggestions kept per seed, and in all.
        'per_seed' => 3,
        'entities' => 8,
        'chronicles' => 4,
        'stories' => 3,
    ],

    'cache' => [
        // Seconds an answer stays in the cache store (CACHE_STORE).
        'on_this_day' => 12 * 3600,
        'meanwhile' => 6 * 3600,
        'quest' => 36 * 3600,
        // An answer with nothing in it (the tile table or the anniversaries
        // not built yet) is kept only this long.
        'empty' => 300,
        // Cache-Control max-age: shared answers, and the per-browser one.
        'max_age' => 300,
        'for_you_max_age' => 60,
    ],

];
