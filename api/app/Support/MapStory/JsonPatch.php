<?php

declare(strict_types=1);

namespace App\Support\MapStory;

use stdClass;

/**
 * RFC 6902 JSON Patch (add, remove, replace, move, copy, test) over a decoded
 * document: stdClass for JSON objects, PHP lists for arrays (MapStoryFile).
 * Paths are RFC 6901 JSON Pointers (`/steps/2/narrative`, `~1` for `/`,
 * `~0` for `~`, `-` appends to a list).
 *
 * apply() works on a copy and returns the patched document, or throws
 * JsonPatchException naming the operation that failed: the ops apply all or
 * none.
 */
final class JsonPatch
{
    public const OPS = ['add', 'remove', 'replace', 'move', 'copy', 'test'];

    /**
     * @param  list<array<string, mixed>>  $ops
     *
     * @throws JsonPatchException
     */
    public static function apply(stdClass $document, array $ops): stdClass
    {
        $doc = MapStoryFile::copy($document);
        foreach (array_values($ops) as $i => $op) {
            $label = "op {$i}";
            if (! is_array($op) || ! in_array($op['op'] ?? null, self::OPS, true)) {
                throw new JsonPatchException("{$label}: `op` must be one of ".implode(', ', self::OPS));
            }
            if (! is_string($op['path'] ?? null)) {
                throw new JsonPatchException("{$label}: `path` must be a JSON Pointer like /steps/0/title");
            }
            $label .= " ({$op['op']} {$op['path']})";
            $path = self::pointer($op['path'], $label);

            switch ($op['op']) {
                case 'add':
                    $doc = self::add($doc, $path, self::value($op, $label), $label);
                    break;
                case 'remove':
                    $doc = self::remove($doc, $path, $label);
                    break;
                case 'replace':
                    self::get($doc, $path, $label);
                    $doc = self::replace($doc, $path, self::value($op, $label), $label);
                    break;
                case 'move':
                case 'copy':
                    if (! is_string($op['from'] ?? null)) {
                        throw new JsonPatchException("{$label}: `from` must be a JSON Pointer");
                    }
                    $from = self::pointer($op['from'], $label);
                    if ($op['op'] === 'move' && count($path) > count($from) && array_slice($path, 0, count($from)) === $from) {
                        throw new JsonPatchException("{$label}: cannot move a value into itself");
                    }
                    $value = MapStoryFile::copy(self::get($doc, $from, $label));
                    if ($op['op'] === 'move') {
                        $doc = self::remove($doc, $from, $label);
                    }
                    $doc = self::add($doc, $path, $value, $label);
                    break;
                case 'test':
                    if (! self::equal(self::get($doc, $path, $label), self::value($op, $label))) {
                        throw new JsonPatchException("{$label}: test failed — the value there is different");
                    }
                    break;
            }
            if (! $doc instanceof stdClass) {
                throw new JsonPatchException("{$label}: the document must stay an object");
            }
        }

        return $doc;
    }

    /** The value at a pointer, or null when there is none. */
    public static function at(mixed $doc, string $pointer): mixed
    {
        try {
            return self::get($doc, self::pointer($pointer, ''), '');
        } catch (JsonPatchException) {
            return null;
        }
    }

    /** @return list<string> */
    private static function pointer(string $pointer, string $label): array
    {
        if ($pointer === '') {
            return [];
        }
        if ($pointer[0] !== '/') {
            throw new JsonPatchException("{$label}: a JSON Pointer starts with /");
        }

        return array_map(fn (string $t) => str_replace(['~1', '~0'], ['/', '~'], $t), array_slice(explode('/', $pointer), 1));
    }

    private static function value(array $op, string $label): mixed
    {
        if (! array_key_exists('value', $op)) {
            throw new JsonPatchException("{$label}: `value` is missing");
        }

        return MapStoryFile::fromArray($op['value']);
    }

    /** @param  list<string>  $path */
    private static function get(mixed $node, array $path, string $label): mixed
    {
        foreach ($path as $token) {
            if ($node instanceof stdClass) {
                if (! property_exists($node, $token)) {
                    throw new JsonPatchException("{$label}: no '{$token}' there");
                }
                $node = $node->{$token};
            } elseif (is_array($node)) {
                $index = self::index($token, count($node), false, $label);
                $node = $node[$index];
            } else {
                throw new JsonPatchException("{$label}: '{$token}' is inside a value that is not an object or list");
            }
        }

        return $node;
    }

    /** @param  list<string>  $path */
    private static function add(mixed $node, array $path, mixed $value, string $label): mixed
    {
        if ($path === []) {
            return $value;
        }
        $token = array_shift($path);
        if ($node instanceof stdClass) {
            if ($path === []) {
                $node->{$token} = $value;

                return $node;
            }
            if (! property_exists($node, $token)) {
                throw new JsonPatchException("{$label}: no '{$token}' there");
            }
            $node->{$token} = self::add($node->{$token}, $path, $value, $label);

            return $node;
        }
        if (is_array($node)) {
            if ($path === []) {
                $index = $token === '-' ? count($node) : self::index($token, count($node), true, $label);
                array_splice($node, $index, 0, [$value]);

                return $node;
            }
            $index = self::index($token, count($node), false, $label);
            $node[$index] = self::add($node[$index], $path, $value, $label);

            return $node;
        }
        throw new JsonPatchException("{$label}: '{$token}' is inside a value that is not an object or list");
    }

    /**
     * Set an existing member in place (an object keeps its key order).
     *
     * @param  list<string>  $path
     */
    private static function replace(mixed $node, array $path, mixed $value, string $label): mixed
    {
        if ($path === []) {
            return $value;
        }
        $token = array_shift($path);
        if ($node instanceof stdClass) {
            $node->{$token} = self::replace($node->{$token}, $path, $value, $label);

            return $node;
        }
        $index = self::index($token, count($node), false, $label);
        $node[$index] = self::replace($node[$index], $path, $value, $label);

        return $node;
    }

    /** @param  list<string>  $path */
    private static function remove(mixed $node, array $path, string $label): mixed
    {
        if ($path === []) {
            throw new JsonPatchException("{$label}: cannot remove the whole document");
        }
        $token = array_shift($path);
        if ($node instanceof stdClass) {
            if (! property_exists($node, $token)) {
                throw new JsonPatchException("{$label}: no '{$token}' there");
            }
            if ($path === []) {
                unset($node->{$token});
            } else {
                $node->{$token} = self::remove($node->{$token}, $path, $label);
            }

            return $node;
        }
        if (is_array($node)) {
            $index = self::index($token, count($node), false, $label);
            if ($path === []) {
                array_splice($node, $index, 1);
            } else {
                $node[$index] = self::remove($node[$index], $path, $label);
            }

            return $node;
        }
        throw new JsonPatchException("{$label}: '{$token}' is inside a value that is not an object or list");
    }

    private static function index(string $token, int $count, bool $insert, string $label): int
    {
        if (! preg_match('/^(0|[1-9][0-9]*)$/', $token)) {
            throw new JsonPatchException("{$label}: '{$token}' is not a list index");
        }
        $index = (int) $token;
        if ($index > $count || (! $insert && $index === $count)) {
            throw new JsonPatchException("{$label}: index {$index} is out of range (the list has {$count})");
        }

        return $index;
    }

    private static function equal(mixed $a, mixed $b): bool
    {
        if ((is_int($a) || is_float($a)) && (is_int($b) || is_float($b))) {
            return $a == $b;
        }
        if ($a instanceof stdClass && $b instanceof stdClass) {
            $va = get_object_vars($a);
            $vb = get_object_vars($b);
            if (count($va) !== count($vb)) {
                return false;
            }
            foreach ($va as $key => $value) {
                if (! array_key_exists($key, $vb) || ! self::equal($value, $vb[$key])) {
                    return false;
                }
            }

            return true;
        }
        if (is_array($a) && is_array($b)) {
            if (count($a) !== count($b)) {
                return false;
            }
            foreach ($a as $i => $value) {
                if (! self::equal($value, $b[$i] ?? null)) {
                    return false;
                }
            }

            return true;
        }

        return $a === $b;
    }
}
