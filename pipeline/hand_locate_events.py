#!/usr/bin/env python3
"""One-off: hand-assigned representative locations (+ years) for well-known event
entities the automated passes couldn't place. Upserts entity_locations.geom and
fills a missing temporal year; run `php artisan entity:backfill` afterwards to
materialise the map geometry. Idempotent. --apply to write."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
_R = Path(__file__).resolve().parent.parent
if str(_R) not in sys.path:
    sys.path.insert(0, str(_R))
import psycopg

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"

# (name, lon, lat, year) — representative location of the event/process.
EVENTS = [
    ("COVID-19", 114.3, 30.6, 2019), ("Crusades_Plague", 35.0, 33.0, 1348),
    ("Dancing mania outbreaks", 7.0, 49.0, 1374), ("measles", 10.0, 48.0, 1850),
    ("Scrofula", 2.3, 48.9, 1200), ("World War I Trench Warfare", 2.9, 49.5, 1916),
    ("Britain Abolishes the Slave Trade", -0.13, 51.5, 1807),
    ("British Empire Abolishes Slavery", -0.13, 51.5, 1833),
    ("Codification of the Twelve Tables", 12.48, 41.9, -451),
    ("End of Apartheid", 28.0, -26.2, 1994), ("Jalali reform", 51.68, 32.65, 1079),
    ("Mexico Abolishes Slavery", -99.13, 19.43, 1829),
    ("Nationalization of Oil in Mexico", -99.13, 19.43, 1938),
    ("Octavian Declared Augustus", 12.48, 41.9, -27),
    ("Presidency of Benito Juárez", -99.13, 19.43, 1858),
    ("The Ides of March", 12.48, 41.9, -44),
    ("Unification of China under Qin Shi Huang", 108.9, 34.3, -221),
    ("United States Bans Importation of Slaves", -77.0, 38.9, 1808),
    ("Bolshevik Revolution", 30.3, 59.94, 1917), ("Boudica’s Rebellion", -1.0, 52.5, 60),
    ("Boudica's Rebellion", -1.0, 52.5, 60), ("Spartacus’ Revolt", 14.0, 41.0, -73),
    ("First War of Indian Independence", 78.0, 27.0, 1857),
    ("Fall of the Yuan Dynasty", 116.4, 39.9, 1368),
    ("Birth of the Modern Calendar", 12.48, 41.9, -45),
    ("Copernicus heliocentric theory", 19.4, 54.36, 1543),
    ("Invention of Television", -0.13, 51.5, 1925),
    ("Iron Metallurgy Spreads; End of Bronze Age, Beginning of Iron Age", 37.0, 39.0, -1200),
    ("The First Wheeled Vehicles Appear", 44.0, 32.0, -4500),
    ("The First Writing Systems Appear", 44.4, 32.5, -3400),
    ("Space Race", -80.6, 28.5, 1957), ("Waldseemüller maps America", 7.0, 48.3, 1507),
    ("Manila galleon trade inaugurated", 120.98, 14.6, 1565),
    ("Council of Trent", 11.12, 46.07, 1545),
    ("The United Nations Is Formed", -122.4, 37.78, 1945),
    ("Alexander's Conquests", 33.0, 35.0, -334),
    ("Alexander the Great Creates an Immense Empire", 33.0, 35.0, -336),
    ("Arab-Israeli Conflicts", 35.0, 31.5, 1948),
    ("Caesar crosses the Rubicon and civil war", 12.4, 44.1, -49),
    ("Crossing of the Rubicon", 12.4, 44.1, -49), ("Fall of the USSR", 37.6, 55.75, 1991),
    ("Hannibal’s Alps Crossing", 7.0, 45.0, -218), ("Napoleonic Wars", 2.35, 48.85, 1803),
    ("Punic Wars", 10.3, 36.9, -264), ("Salem witch trials", -70.9, 42.5, 1692),
    ("September 11, 2001 CE", -74.0, 40.7, 2001),
    ("The American Civil War: 1860–1865", -79.0, 37.5, 1861),
    ("The Cold War: 1945–1989", 13.4, 52.5, 1947), ("The Holocaust", 19.2, 50.0, 1941),
    ("Trojan War", 26.24, 39.96, -1250), ("Vietnam War", 106.0, 16.0, 1955),
    ("World War II", 13.4, 52.5, 1939), ("Haiti independence", -72.3, 18.5, 1804),
    ("Global Depression (1929–1940)", -74.0, 40.7, 1929),
    ("First circumnavigation of the globe (Magellan)", -52.0, -52.0, 1519),
    ("Mongol conquest of Song", 109.0, 30.0, 1235),
    ("Council of Trent", 11.12, 46.07, 1545),
    ("Fake Trees in World War I", 2.9, 49.5, 1916),
    ("Operation Acoustic Kitty", -77.0, 38.9, 1962),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = psycopg.connect(DSN); cur = conn.cursor()
    done, missing = 0, []
    for name, lon, lat, year in EVENTS:
        cur.execute("SELECT entity_id FROM entities WHERE name=%s AND (entity_type::text LIKE 'event_%%' OR entity_type::text IN ('migration','epidemic_disease'))", (name,))
        r = cur.fetchall()
        if not r:
            missing.append(name); continue
        for (eid,) in r:
            if args.apply:
                cur.execute("""
                    INSERT INTO entity_locations (location_id, entity_id, geom, location_method, is_primary, created_at, updated_at)
                    VALUES (gen_random_uuid(), %s, ST_SetSRID(ST_MakePoint(%s,%s),4326), 'human_assigned', true, now(), now())
                    ON CONFLICT (entity_id) WHERE is_primary DO UPDATE SET geom=EXCLUDED.geom, location_method='human_assigned', updated_at=now()
                """, (eid, lon, lat))
                cur.execute("""
                    INSERT INTO entity_temporal_ranges (temporal_range_id, entity_id, range_type, start_year, end_year, start_date, is_primary, created_at, updated_at)
                    VALUES (gen_random_uuid(), %s, 'primary', %s, %s, %s, true, now(), now())
                    ON CONFLICT (entity_id) WHERE is_primary DO UPDATE
                      SET start_year=COALESCE(entity_temporal_ranges.start_year, EXCLUDED.start_year),
                          start_date=COALESCE(entity_temporal_ranges.start_date, EXCLUDED.start_date), updated_at=now()
                """, (eid, year, year, str(year)))
            done += 1
    if args.apply:
        conn.commit()
    print(f"{'Applied' if args.apply else 'Would apply'} {done} event locations; {len(missing)} names not found: {missing}")
    conn.close(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
