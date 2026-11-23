<?php

declare(strict_types=1);

namespace App\Support\Tags;

use App\Enums\EntityType;

/**
 * Where each region tag lies on the map, coarsely: a few boxes in degrees
 * (docs/architecture/tags.md, "Region footprints").
 *
 * DeriveTagsAction uses it so that an entity with a place of its own does not
 * inherit a region from a chronicle when that place is nowhere near the
 * region: the First Battle of Ypres is in a World War I chronicle tagged
 * Europe, Asia and the Middle East, and keeps only Europe.
 *
 * A region's footprint is its own boxes plus those of every region inside it,
 * so Asia is Siberia plus the Middle East, Central Asia and the rest, and a
 * parent always covers its children. Boxes follow the region's real edges and
 * overlap freely; an overlap only means a tag is kept. TOLERANCE widens every
 * box, so a point just past an edge still counts. A region with no boxes of
 * its own or below it (Global) has no footprint and is never dropped.
 */
final class RegionFootprint
{
    /** Degrees added on every side of every box (about 50 km). */
    public const TOLERANCE = 0.5;

    /**
     * Types whose map point is where the thing is. Others are left alone: a
     * person's point is a birthplace, a treaty's the place it was signed, and
     * a war, polity or movement spreads far beyond its one point.
     *
     * @var list<EntityType>
     */
    public const POINT_TYPES = [
        EntityType::EventBattle,
        EntityType::City,
        EntityType::InfrastructureMonument,
        EntityType::EducationalInstitution,
        EntityType::ExtractionInfra,
    ];

    /**
     * Region slug => its own boxes, each [west, south, east, north] in degrees.
     * An empty list: the region is only the regions inside it.
     *
     * @var array<string, list<array{int|float, int|float, int|float, int|float}>>
     */
    public const BOXES = [
        // Africa
        'africa' => [],
        'north-africa' => [
            [-18.5, 14.5, -1.8, 35.95],    // Morocco, Western Sahara, Mauritania, the Canaries
            [-1.8, 14.5, 11.6, 37.4],      // Algeria, Tunisia
            [11.6, 14.5, 25.2, 33.3],      // Libya
            ...self::EGYPT,
        ],
        'egypt' => self::EGYPT,
        'nubia' => [
            [21.5, 3.5, 36, 24.5],
            [36, 3.5, 38.6, 22.3],         // the Red Sea coast
        ],
        'west-africa' => [
            [-25.5, 3.5, 16, 25.5],
            [16, 10, 24, 25.5],            // Chad, the eastern Sahel
            [-17.5, 25.5, -4.8, 27.3],     // northern Mauritania
        ],
        'east-africa' => [
            [28.5, -12.5, 51.5, 12],
            [32, 12, 43.3, 18.1],          // Ethiopia, Eritrea
            [43, -25.7, 58, -3.5],         // Madagascar, the Mascarenes, the Seychelles
        ],
        'central-africa' => [[5.5, -13.5, 31.4, 23.5]],
        'southern-africa' => [
            [11.5, -35, 33.5, -8],
            [33.5, -35, 41, -10.4],        // Malawi, Mozambique
            [11.5, -8, 24.1, -4.3],        // northern Angola
            [43, -25.7, 50.6, -11.9],      // Madagascar
        ],

        // The Americas
        'americas' => [],
        'north-america' => [
            [-180, 50, -50, 84],           // Alaska, Canada
            [-140, 14.5, -50, 50],         // the United States, Mexico, Bermuda
            [-75, 59, -30, 84],            // Greenland
            [-30, 67, -10, 84],
            [-161, 18.5, -154.5, 22.5],    // Hawaii
            [172, 51, 180, 55],            // the western Aleutians
        ],
        'mesoamerica' => [
            [-118, 22.8, -106, 32.7],      // north-western Mexico
            [-106, 22.8, -97, 29.4],       // north-eastern Mexico
            [-106, 14.5, -86.7, 22.8],     // central and southern Mexico, the Maya lands
            [-89, 14.5, -83, 16.5],        // the Honduran coast
            [-92.5, 7, -77, 14.5],         // Central America
        ],
        'caribbean' => [[-90, 9.5, -58.5, 27.5]],
        'south-america' => [
            [-92.5, -56, -77.2, 6.5],      // the Pacific coast, the Galápagos
            [-77.2, -56, -32, 13],
        ],
        'andes' => [
            [-81.5, -6, -66, 11.5],
            [-81.5, -25, -63, -6],
            [-76, -56, -64, -25],
        ],

        // Asia
        'asia' => [
            [60, 50, 180, 82],             // Siberia
            [-180, 62, -168, 72],          // Chukotka
        ],
        'middle-east' => [],
        'mesopotamia' => [
            [38, 29.5, 45.8, 38.3],
            [45.8, 28.5, 49, 33.5],        // Sumer, Susiana
        ],
        'levant' => [
            [34.2, 29.2, 39.3, 37.3],
            [39.3, 32.3, 42.4, 37.3],      // eastern Syria
            [32.2, 34.5, 34.7, 35.75],     // Cyprus
        ],
        'anatolia' => [
            [25.9, 36.6, 41, 42.2],
            [41, 37.1, 43.6, 41.6],
            [43.6, 37.1, 44.8, 40.1],
            [26.5, 35.8, 37, 36.6],        // Lycia, Cilicia, Hatay
        ],
        'arabia' => [
            [34.5, 24, 36.5, 30.5],        // Midian, Petra, Aqaba
            [36.5, 24, 48.5, 32.2],        // the Nafud, Kuwait
            [38.5, 16.5, 56.5, 24],        // the Hejaz, Najd
            [42.5, 12, 60, 19],            // Yemen, Hadramawt, Dhofar
            [48.5, 19, 60, 27],            // the Gulf coast, Oman
        ],
        'iran' => [
            [44, 30, 71.5, 42.5],          // with Khorasan, Khwarazm, Sogdia, Bactria
            [50, 27, 71.5, 30],
            [57, 25, 71.5, 27],
        ],
        'caucasus' => [
            [37.2, 41.3, 50.5, 46],
            [42.3, 38.3, 48.5, 41.3],      // the Armenian highlands
        ],
        'central-asia' => [
            [50, 36.5, 87.5, 56],          // Turkestan, the Kazakh steppe
            [60.5, 29.4, 71.7, 38.5],      // Afghanistan, Bactria
            [71.7, 35.5, 75, 38.5],        // the Pamirs
            [73.5, 35.5, 98, 49.2],        // the Tarim basin, Dzungaria, the Gansu corridor
            [85, 41, 122, 54],             // Mongolia
            [28, 44, 56, 53],              // the Pontic-Caspian steppe
        ],
        'south-asia' => [
            [60.5, -1, 92.7, 37.1],
            [92.7, 23.5, 97.5, 29.5],      // Assam
            [91, 21.9, 93.5, 24.5],
        ],
        'southeast-asia' => [
            [92, 9.5, 98.8, 28.6],         // Burma
            [98.8, 19.3, 101.2, 24.2],
            [97.3, 5.5, 109.5, 23.4],      // Thailand, Laos, Cambodia, Vietnam
            [94.9, -11.5, 141.1, 7.5],     // the Malay world, Indonesia
            [116.9, 4.5, 127, 21.2],       // the Philippines
        ],
        'east-asia' => [
            [87.5, 41.5, 120, 52.2],       // Mongolia
            [120, 42, 142, 55],            // Manchuria, the Amur, Sakhalin
        ],
        'china' => [
            [73.5, 35, 124.5, 41],         // Kashgar to the Yellow Sea
            [79.8, 41, 96.5, 49.2],        // Dzungaria
            [96.5, 41, 115.5, 43],         // Inner Mongolia
            [115.5, 41, 135.1, 53.6],      // Manchuria
            [78.4, 28.5, 123, 35],         // Tibet to Shanghai
            [97.3, 22, 123, 28.5],         // the south
            [106.5, 21.5, 123, 22],
            [108.5, 18, 117.5, 21.5],      // Hainan
            [119.3, 21.8, 122.1, 25.4],    // Taiwan
        ],
        'japan' => [
            [122.9, 24, 131.5, 30.5],      // the Ryukyus
            [129, 30.5, 132.1, 34.3],      // Kyushu, Tsushima
            [130.8, 33.2, 142.1, 41.6],    // Honshu, Shikoku
            [139.3, 41.3, 146, 45.6],      // Hokkaido
            [139, 24, 142.5, 33.2],        // the Izu and Bonin islands
            [141, 45.6, 156.5, 50.5],      // Karafuto, the Kurils
        ],
        'korea' => [
            [124, 33, 127.5, 43.1],
            [127.5, 34.3, 129.6, 43.1],
            [129.6, 35.5, 131, 43.1],
            [121, 38.7, 131, 45],          // Liaodong and Manchuria: Goguryeo, Balhae
        ],

        // Europe
        'europe' => [],
        'british-isles' => [
            [-10.7, 50.55, 1.9, 61],
            [-6.5, 49.85, -2.5, 50.55],    // Cornwall, Scilly
            [-2.8, 49.1, -2, 49.8],        // the Channel Islands
        ],
        'western-europe' => [
            [-5.2, 46, -1.8, 49.75],       // Brittany
            [-1.8, 42.3, 1.6, 49.75],
            [1.6, 42.3, 8.3, 53.6],        // to the Rhineland and Frisia
            [8.5, 41.3, 9.6, 43.1],        // Corsica
        ],
        'iberia' => [
            [-9.6, 35.9, -1.8, 43.9],
            [-1.8, 35.9, 4.4, 42.9],
        ],
        'italy' => [
            [7, 43.7, 13.9, 46],           // the north
            [8.4, 46, 10.4, 46.6],         // the lakes, Valtellina
            [10.4, 46, 12.5, 46.75],       // Trentino, South Tyrol
            [12.5, 46, 13.9, 46.65],       // Friuli
            [9, 39.8, 15.8, 44.5],         // the centre, Rome, Naples
            [15.8, 39.8, 18.6, 42],        // Apulia
            [12, 36.5, 17.2, 39.8],        // Calabria, Sicily
            [8, 38.8, 9.9, 41.3],          // Sardinia
            [11.9, 35.4, 14.6, 36.9],      // Malta, Pantelleria, Lampedusa
        ],
        'central-europe' => [
            [5.8, 46.3, 26.5, 55.1],
            [13.4, 45.4, 26.5, 46.3],      // Carniola, Croatia, southern Hungary
        ],
        'eastern-europe' => [
            [20, 44.3, 87, 82],            // Ukraine, Belarus, Russia to western Siberia
            [36.5, 41, 50, 44.3],          // the Caucasus
            [87, 49.5, 180, 82],           // Siberia
            [131, 42.3, 141.5, 48.5],      // Primorye
            [130, 47.5, 141.5, 49.5],      // the Amur
            [141.5, 45.8, 145, 49.5],      // Sakhalin
            [145.8, 43.4, 157, 49.5],      // the Kurils
            [-180, 62, -168, 72],          // Chukotka
        ],
        'northern-europe' => [
            [4.5, 53.8, 32, 71.5],         // Scandinavia, Finland, the Baltic
            [-25, 63, -13, 67],            // Iceland
            [-8, 61, -6, 63],              // the Faroes
            [10, 76, 35, 81],              // Svalbard
        ],
        'balkans' => [
            [13.3, 44.5, 30.3, 46],
            [14.8, 42.2, 30.3, 44.5],
            [21, 46, 30.3, 48.6],          // Transylvania, Moldavia
            [13.3, 46, 16.6, 46.9],        // Slovenia
            [18.9, 39.4, 30.3, 42.2],
            [19.3, 36.3, 24.7, 39.4],      // mainland Greece
        ],
        'greece' => [
            [19.3, 34.7, 29.3, 41.8],      // with Ionia and Byzantium
            [32.2, 34.5, 34.7, 35.75],     // Cyprus
        ],

        // Across regions
        'oceania' => [
            [129, -55, 180, 30],           // Melanesia, Micronesia, New Zealand
            [112, -45, 129, -10],          // western Australia
            [-180, -55, -105, 30],         // Polynesia, Hawaii, Rapa Nui
        ],
        'mediterranean' => [[-10, 29.5, 37, 46.5]],
        'indian-ocean' => [
            [17, -45, 121, 31.5],
            [121, -11, 135, 5],            // Sulawesi, the Moluccas: the spice trade
        ],
        'atlantic' => [[-100, -56, 20, 72]],
        'silk-roads' => [[12, 20, 136, 50]],
        'polar' => [
            [-180, 60, 180, 90],
            [-180, -90, 180, -50],
        ],
    ];

    /** @var list<array{int|float, int|float, int|float, int|float}> */
    private const EGYPT = [
        [24.5, 21.5, 34.3, 31.7],
        [34.3, 27.7, 35, 29.6],            // south-eastern Sinai
        [34.3, 21.5, 36, 26.5],            // the Red Sea coast
    ];

    /**
     * A query yielding `(tag, box)`: every region with each of its own boxes
     * and those of the regions inside it (from `tags.parent_slug`), widened by
     * TOLERANCE, as SRID 4326 envelopes.
     */
    public static function sql(): string
    {
        return sprintf(<<<'SQL'
            WITH RECURSIVE tree AS (
                SELECT slug AS region, slug FROM tags WHERE facet = 'region'
                UNION
                SELECT tree.region, t.slug FROM tree JOIN tags t ON t.parent_slug = tree.slug
            ),
            boxes (slug, w, s, e, n) AS (VALUES %s)
            SELECT tree.region AS tag, ST_MakeEnvelope(b.w, b.s, b.e, b.n, 4326) AS box
            FROM tree JOIN boxes b ON b.slug = tree.slug
            SQL, self::valuesSql());
    }

    /** The point types as a SQL list of quoted enum values. */
    public static function pointTypesSql(): string
    {
        return implode(', ', array_map(fn (EntityType $t): string => "'{$t->value}'", self::POINT_TYPES));
    }

    /**
     * Every own box, widened by TOLERANCE, as SQL VALUES rows
     * `(slug, west, south, east, north)`. The numbers are constants, so they
     * are written inline.
     */
    private static function valuesSql(): string
    {
        $rows = [];
        foreach (self::BOXES as $slug => $boxes) {
            foreach ($boxes as [$west, $south, $east, $north]) {
                $rows[] = sprintf(
                    "('%s', %s, %s, %s, %s)",
                    $slug,
                    self::number($west - self::TOLERANCE),
                    self::number($south - self::TOLERANCE),
                    self::number($east + self::TOLERANCE),
                    self::number($north + self::TOLERANCE),
                );
            }
        }

        return implode(",\n", $rows);
    }

    private static function number(int|float $degrees): string
    {
        return sprintf('%.4F::float8', $degrees);
    }
}
