<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Scope;

use App\Enums\EntityGroup;
use App\Enums\EntityType;
use InvalidArgumentException;

/**
 * A parsed, fully validated `--scope` selection for `content:export`. Everything (uuids, enum
 * values, slugs, year ranges, `ids:` files) is checked here so the resolver never feeds Postgres a bad cast.
 *
 * Security: the API must build scopes from allowlisted kinds and never pass raw request strings.
 * `ids:` reads a local file, so it is refused unless the caller (the CLI) opts in.
 */
final class ExportScope
{
    private const UUID = '/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\z/';

    /** Must equal `$defs/year` in common.schema.json (asserted by a test). */
    public const YEAR_MIN = -20000;

    public const YEAR_MAX = 3000;

    /** Must equal `$defs/slug` in common.schema.json (asserted by a test). */
    public const SLUG_PATTERN = '^[^\sA-Z/]+$';

    public const SLUG_MAX_LENGTH = 255;

    private const IDS_FILE_MAX_BYTES = 10 * 1024 * 1024;

    /**
     * @param  list<string>  $specs  normalised specs, input order, no duplicates
     * @param  list<string>  $chronicleSlugs
     * @param  list<string>  $entityIds  from `entity:` specs and `ids:` files
     * @param  list<string>  $neighbourIds
     * @param  list<string>  $types
     * @param  list<string>  $groups
     * @param  list<array{int, int}>  $yearRanges
     */
    private function __construct(
        private readonly array $specs,
        private readonly bool $all,
        private readonly array $chronicleSlugs,
        private readonly array $entityIds,
        private readonly array $neighbourIds,
        private readonly array $types,
        private readonly array $groups,
        private readonly array $yearRanges,
    ) {}

    /**
     * @param  list<string>  $specs  `[]` means `all`
     * @param  bool  $allowIdsFiles  only the command line passes true
     */
    public static function parse(array $specs, bool $allowIdsFiles = false): self
    {
        $normalised = [];
        $slugs = $entityIds = $neighbourIds = $types = $groups = $ranges = [];
        $all = $specs === [];

        foreach ($specs as $spec) {
            if ($spec === 'all') {
                $all = true;
                $normalised[] = 'all';

                continue;
            }
            $pos = strpos($spec, ':');
            if ($pos === false) {
                throw new InvalidArgumentException("Unknown scope spec \"{$spec}\".");
            }
            $kind = substr($spec, 0, $pos);
            $value = substr($spec, $pos + 1);

            switch ($kind) {
                case 'chronicle':
                    if (! self::validSlug($value)) {
                        throw new InvalidArgumentException("Invalid chronicle slug in scope spec \"{$spec}\".");
                    }
                    $slugs[] = $value;
                    $normalised[] = "chronicle:{$value}";
                    break;
                case 'entity':
                    $id = self::uuid($value, $spec);
                    $entityIds[] = $id;
                    $normalised[] = "entity:{$id}";
                    break;
                case 'neighbours':
                    $id = self::uuid($value, $spec);
                    $neighbourIds[] = $id;
                    $normalised[] = "neighbours:{$id}";
                    break;
                case 'type':
                    $list = [];
                    foreach (explode(',', $value) as $t) {
                        if (EntityType::tryFrom($t) === null) {
                            throw new InvalidArgumentException("Unknown entity type \"{$t}\" in scope spec \"{$spec}\".");
                        }
                        $list[] = $t;
                    }
                    $list = array_values(array_unique($list));
                    $types = [...$types, ...$list];
                    $normalised[] = 'type:'.implode(',', $list);
                    break;
                case 'group':
                    if (EntityGroup::tryFrom($value) === null) {
                        throw new InvalidArgumentException("Unknown entity group \"{$value}\" in scope spec \"{$spec}\".");
                    }
                    $groups[] = $value;
                    $normalised[] = "group:{$value}";
                    break;
                case 'years':
                    if (! preg_match('/^([+-]?\d+)\.\.([+-]?\d+)\z/', $value, $m)) {
                        throw new InvalidArgumentException("Invalid year range in scope spec \"{$spec}\"; expected years:<from>..<to>.");
                    }
                    [$from, $to] = [self::year($m[1], $spec), self::year($m[2], $spec)];
                    if ($from > $to) {
                        throw new InvalidArgumentException("Year range in scope spec \"{$spec}\" has from greater than to.");
                    }
                    $ranges[] = [$from, $to];
                    $normalised[] = "years:{$from}..{$to}";
                    break;
                case 'ids':
                    if (! $allowIdsFiles) {
                        throw new InvalidArgumentException("Invalid scope spec \"{$spec}\": ids: lists are only available from the command line.");
                    }
                    $entityIds = [...$entityIds, ...self::readIds($value)];
                    $normalised[] = 'ids:'.basename($value);
                    break;
                default:
                    throw new InvalidArgumentException("Unknown scope spec \"{$spec}\".");
            }
        }

        $uniq = fn (array $a) => array_values(array_unique($a, SORT_REGULAR));

        return new self(
            $all ? ['all'] : $uniq($normalised),
            $all,
            $uniq($slugs),
            $uniq($entityIds),
            $uniq($neighbourIds),
            $uniq($types),
            $uniq($groups),
            $uniq($ranges),
        );
    }

    /** @return list<string> normalised specs for the manifest */
    public function specs(): array
    {
        return $this->specs;
    }

    public function isAll(): bool
    {
        return $this->all;
    }

    /** @return list<string> */
    public function chronicleSlugs(): array
    {
        return $this->chronicleSlugs;
    }

    /** @return list<string> */
    public function entityIds(): array
    {
        return $this->entityIds;
    }

    /** @return list<string> */
    public function neighbourIds(): array
    {
        return $this->neighbourIds;
    }

    /** @return list<string> */
    public function types(): array
    {
        return $this->types;
    }

    /** @return list<string> */
    public function groups(): array
    {
        return $this->groups;
    }

    /** @return list<array{int, int}> */
    public function yearRanges(): array
    {
        return $this->yearRanges;
    }

    private static function uuid(string $value, string $spec): string
    {
        $id = strtolower($value);
        if (! preg_match(self::UUID, $id)) {
            throw new InvalidArgumentException("Invalid uuid in scope spec \"{$spec}\".");
        }

        return $id;
    }

    private static function validSlug(string $slug): bool
    {
        return mb_strlen($slug) <= self::SLUG_MAX_LENGTH
            && preg_match('~'.substr(self::SLUG_PATTERN, 0, -1).'\z~', $slug) === 1;
    }

    private static function year(string $digits, string $spec): int
    {
        $number = ltrim($digits, '+-');
        $out = strlen(ltrim($number, '0')) > 6 ? null : (int) $digits;
        if ($out === null || $out < self::YEAR_MIN || $out > self::YEAR_MAX) {
            throw new InvalidArgumentException('Year out of range '.self::YEAR_MIN.'..'.self::YEAR_MAX." in scope spec \"{$spec}\".");
        }

        return $out;
    }

    /** @return list<string> */
    private static function readIds(string $path): array
    {
        $name = basename($path);
        $raw = is_file($path) && is_readable($path) && filesize($path) <= self::IDS_FILE_MAX_BYTES
            ? @file_get_contents($path, false, null, 0, self::IDS_FILE_MAX_BYTES + 1)
            : false;
        if ($raw === false || strlen($raw) > self::IDS_FILE_MAX_BYTES) {
            throw new InvalidArgumentException("Invalid ids: cannot read ids file {$name}.");
        }

        $ids = [];
        foreach (preg_split('/\r?\n/', $raw) as $i => $line) {
            $line = trim($line);
            if ($line === '' || str_starts_with($line, '#')) {
                continue;
            }
            $id = strtolower($line);
            if (! preg_match(self::UUID, $id)) {
                throw new InvalidArgumentException('Invalid ids file '.$name.': line '.($i + 1).' is not a uuid.');
            }
            $ids[] = $id;
        }

        return $ids;
    }
}
