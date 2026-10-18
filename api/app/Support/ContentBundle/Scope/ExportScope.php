<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Scope;

use App\Enums\EntityGroup;
use App\Enums\EntityType;
use InvalidArgumentException;

/**
 * A parsed, fully validated `--scope` selection for `content:export`. Everything (uuids, enum
 * values, year ranges, `ids:` files) is checked here so the resolver never feeds Postgres a bad cast.
 */
final class ExportScope
{
    private const UUID = '/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/';

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
     */
    public static function parse(array $specs): self
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
                    if ($value === '' || preg_match('/\s/', $value)) {
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
                    if (! preg_match('/^([+-]?\d+)\.\.([+-]?\d+)$/', $value, $m)) {
                        throw new InvalidArgumentException("Invalid year range in scope spec \"{$spec}\"; expected years:<from>..<to>.");
                    }
                    [$from, $to] = [(int) $m[1], (int) $m[2]];
                    if ($from > $to) {
                        throw new InvalidArgumentException("Year range in scope spec \"{$spec}\" has from greater than to.");
                    }
                    $ranges[] = [$from, $to];
                    $normalised[] = "years:{$from}..{$to}";
                    break;
                case 'ids':
                    $entityIds = [...$entityIds, ...self::readIds($value, $spec)];
                    $normalised[] = $spec;
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

    /** @return list<string> */
    private static function readIds(string $path, string $spec): array
    {
        $lines = $path === '' || ! is_file($path) || ! is_readable($path) ? false : file($path, FILE_IGNORE_NEW_LINES);
        if ($lines === false) {
            throw new InvalidArgumentException("Cannot read ids file \"{$path}\" in scope spec \"{$spec}\".");
        }

        $ids = [];
        foreach ($lines as $i => $line) {
            $line = trim($line);
            if ($line === '' || str_starts_with($line, '#')) {
                continue;
            }
            $id = strtolower($line);
            if (! preg_match(self::UUID, $id)) {
                throw new InvalidArgumentException('Line '.($i + 1)." of ids file \"{$path}\" is not a uuid: \"{$line}\".");
            }
            $ids[] = $id;
        }

        return $ids;
    }
}
