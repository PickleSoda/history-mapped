<?php

declare(strict_types=1);

use App\Support\TimelineRebuild;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Corrections to records an outside review of the public site found wrong
 * (22 November 2026), each checked against its sources. The dates come from
 * an audit of every day-precise "on this day" date in East Asia before the
 * Western calendar was adopted there (42 checked; the full review with a
 * source per row is output/audit/lunar-dates-20261122/review.csv on the
 * machine that made it, outside git). Each entry below names its reason.
 *
 * Production's content is a copy of the local database, so the ids are the
 * same in both. Each change is guarded on the value it replaces: it applies
 * once, and a record edited since is left alone. Nothing is undone on
 * rollback; a correction is not a schema change.
 */
return new class extends Migration
{
    /**
     * [entity id, column of its primary temporal range, wrong value, right value].
     * A right value without a day drops a day the sources do not support.
     *
     * @var list<array{0: string, 1: string, 2: string, 3: string}>
     */
    private const DATES = [
        // Nagaoka-kyō: the move to Heian-kyō, Enryaku 13, 10th month, 22nd day = 18 November 794 (Julian).
        ['2f9ee104-572e-452c-942f-8eee6d974620', 'end_date', '0794-11-22', '0794-11-18'],
        // Japan, legendary founding: 11 February is the Meiji (proleptic Gregorian) date; Julian is 18 February.
        ['c842e8db-5ec4-4f63-af2a-2d160dce8f3a', 'start_date', '-0660-02-11', '-0660-02-18'],
        // Mutsu Province: divided on Meiji 1, 12th month, 7th day = 19 January 1869.
        ['0b7b6938-d960-4ac1-af27-63857c33daaf', 'end_date', '1869-01-18', '1869-01-19'],
        // Satsuma Rebellion: ended 24 September 1877 (30 September was a month-end fill).
        ['8c56bc41-fe64-4d06-9209-5da62ad05cc8', 'end_date', '1877-09-30', '1877-09-24'],
        // Wihwado: the island carries the Wihwado Retreat's date, a lunar day stored as Julian. Keep the year.
        ['7222722e-4164-4889-bb41-0c4a81012cd6', 'start_date', '1388-06-03', '1388'],
        // Capture of Haozhou: the day rests on one uncited sentence.
        ['2b62daa5-463d-4b02-bfdf-45c23fc1a842', 'start_date', '1352-02-16', '1352-02'],
        ['2b62daa5-463d-4b02-bfdf-45c23fc1a842', 'end_date', '1352-02-16', '1352-02'],
        // Treaty of Nerchinsk: 27 August is the Russian Old Style date; Gregorian is 6 September.
        ['548796a1-4b5b-4e64-a6a5-02674ecaf84d', 'start_date', '1689-08-27', '1689-09-06'],
        ['548796a1-4b5b-4e64-a6a5-02674ecaf84d', 'end_date', '1689-08-27', '1689-09-06'],
        // Guangzhouwan: sources give 19 or 20 February 1900.
        ['4b7c376a-cfac-4254-adbd-ad1054bdfb69', 'start_date', '1900-02-19', '1900-02'],
        // Revive China Society: merged into the Tongmenghui on 20 August 1905 (30 July was a preparatory meeting).
        ['beaf6cc7-01e7-48f1-810f-9f25b2ac46ff', 'end_date', '1905-07-30', '1905-08-20'],
        // Later Lê dynasty: no source gives the day of its end.
        ['723bdc68-505b-465f-b15e-33e313ea6952', 'end_date', '1789-02-03', '1789'],
    ];

    /** First Battle of Ypres: Wikidata's image (P18) is a photograph from the Somme, July 1916. */
    private const YPRES = '1044997b-c484-4a3c-be35-e8760f434532';

    private const YPRES_WRONG_FILE = 'Cheshire Regiment trench Somme 1916.jpg';

    /** The painting at the head of the battle's English Wikipedia article (public domain), as the admin's image picker stores it. */
    private const YPRES_IMAGE = [
        'type' => 'image',
        'kind' => 'image',
        'url' => 'https://upload.wikimedia.org/wikipedia/commons/e/eb/2nd_Ox_%26_Bucks%2C_Nonne_Bosschen%2C_defeating_the_Prussian_Guard_1914_by_W.B._Wollen.jpeg',
        'original_url' => 'https://upload.wikimedia.org/wikipedia/commons/e/eb/2nd_Ox_%26_Bucks%2C_Nonne_Bosschen%2C_defeating_the_Prussian_Guard_1914_by_W.B._Wollen.jpeg',
        'page_url' => 'https://commons.wikimedia.org/wiki/File:2nd_Ox_%26_Bucks,_Nonne_Bosschen,_defeating_the_Prussian_Guard_1914_by_W.B._Wollen.jpeg',
        'file' => '2nd Ox & Bucks, Nonne Bosschen, defeating the Prussian Guard 1914 by W.B. Wollen.jpeg',
        'caption' => '2nd Oxfordshire and Buckinghamshire Light Infantry fight the Prussian Guard at the Battle of Nonne Bosschen, 11 November 1914.',
        'author' => 'William Barnes Wollen',
        'license' => 'Public domain',
        'attribution_required' => false,
        'width' => 960,
        'height' => 636,
        'source' => 'commons',
        'fetched_at' => '2026-11-22T13:44:59+00:00',
    ];

    public function up(): void
    {
        TimelineRebuild::withoutRebuilds(function (): void {
            foreach (self::DATES as [$entityId, $column, $wrong, $right]) {
                $updated = DB::table('entity_temporal_ranges')
                    ->where('entity_id', $entityId)
                    ->where('is_primary', true)
                    ->where($column, $wrong)
                    ->update([$column => $right, 'updated_at' => now()]);

                if ($updated > 0) {
                    // "On this day" keeps a copy of each day; the weekly rebuild
                    // adds the corrected ones back.
                    DB::table('discover_anniversaries')->where('entity_id', $entityId)->where('date', $wrong)->delete();
                    TimelineRebuild::queue($entityId);
                }
            }
        });

        $this->replaceYpresImage();
    }

    public function down(): void
    {
        // Corrections stay.
    }

    private function replaceYpresImage(): void
    {
        $row = DB::table('entities')->where('entity_id', self::YPRES)->first(['attributes']);
        $attributes = $row !== null ? json_decode((string) $row->attributes, true) : null;
        $media = is_array($attributes) ? ($attributes['media_refs'] ?? null) : null;

        if (! is_array($media) || ($media[0]['file'] ?? null) !== self::YPRES_WRONG_FILE) {
            return;
        }

        $kept = array_values(array_filter($media, fn ($item): bool => ($item['file'] ?? null) !== self::YPRES_WRONG_FILE));

        // Marked curated, so the image fetcher never puts Wikidata's picture back.
        DB::update(
            "UPDATE entities SET attributes = attributes || jsonb_build_object('media_refs', ?::jsonb, '_media_curated_at', ?::text), updated_at = now() WHERE entity_id = ?",
            [
                json_encode([self::YPRES_IMAGE, ...$kept], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
                '2026-11-22T14:00:00+00:00',
                self::YPRES,
            ],
        );
    }
};
