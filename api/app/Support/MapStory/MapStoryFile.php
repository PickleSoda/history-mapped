<?php

declare(strict_types=1);

namespace App\Support\MapStory;

use stdClass;

/**
 * A map-story document as text: the exact format the pipeline builder writes
 * (`json.dumps(doc, ensure_ascii=False, indent=1) + "\n"`), and the authored
 * document behind a stored one.
 *
 * Documents travel as decoded objects (stdClass for JSON objects, PHP lists
 * for arrays) so the authored key order and empty objects survive; floats are
 * kept as floats (`12.0` stays `12.0`).
 */
final class MapStoryFile
{
    /** How story JSON is encoded everywhere (files, the DB, revisions). */
    public const JSON_FLAGS = JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION | JSON_UNESCAPED_LINE_TERMINATORS;

    /** Step (and beat) members that are maps by id, never lists. */
    private const MAP_KEYS = ['positions', 'features', 'terrain_state'];

    /** The file content: one-space indented JSON and a trailing newline, as the builder writes it. */
    public static function encode(stdClass $doc): string
    {
        $json = (string) json_encode($doc, self::JSON_FLAGS | JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR);

        // Newlines inside strings are escaped, so every line starts with indentation only.
        return preg_replace_callback('/^(?: {4})+/m', fn (array $m) => str_repeat(' ', intdiv(strlen($m[0]), 4)), $json)."\n";
    }

    /** A JSON object as a document; null when the text is not a JSON object. */
    public static function decode(string $json): ?stdClass
    {
        $doc = json_decode($json);

        return json_last_error() === JSON_ERROR_NONE && $doc instanceof stdClass ? $doc : null;
    }

    /** The hash `file_hash` holds: of a file's bytes, or of what export would write. */
    public static function hash(string $content): string
    {
        return sha1($content);
    }

    /**
     * The same document as nested arrays (for MapStoryDocument and the
     * warnings, which read arrays).
     *
     * @return array<string, mixed>
     */
    public static function toArray(stdClass $doc): array
    {
        return json_decode((string) json_encode($doc, self::JSON_FLAGS), true);
    }

    /** A deep copy, so a patch or a strip never touches the original. */
    public static function copy(mixed $value): mixed
    {
        if ($value instanceof stdClass) {
            $out = new stdClass;
            foreach (get_object_vars($value) as $key => $item) {
                $out->{$key} = self::copy($item);
            }

            return $out;
        }

        return is_array($value) ? array_map(self::copy(...), $value) : $value;
    }

    /**
     * Any JSON-like value as a document tree: associative arrays become
     * objects, lists stay lists. (An empty PHP array is ambiguous: it stays a
     * list; normaliseMaps() turns the known maps back into objects.)
     */
    public static function fromArray(mixed $value): mixed
    {
        if ($value instanceof stdClass) {
            return self::copy($value);
        }
        if (is_array($value)) {
            if ($value !== [] && ! array_is_list($value)) {
                $out = new stdClass;
                foreach ($value as $key => $item) {
                    $out->{$key} = self::fromArray($item);
                }

                return $out;
            }

            return array_map(self::fromArray(...), $value);
        }

        return $value;
    }

    /**
     * Turn the step and beat maps (`positions`, `features`, `terrain_state`)
     * that arrived as empty lists back into empty objects.
     */
    public static function normaliseMaps(stdClass $doc): stdClass
    {
        foreach (is_array($doc->steps ?? null) ? $doc->steps : [] as $step) {
            if (! $step instanceof stdClass) {
                continue;
            }
            self::mapsOf($step);
            foreach (is_array($step->beats ?? null) ? $step->beats : [] as $beat) {
                if ($beat instanceof stdClass) {
                    self::mapsOf($beat);
                }
            }
        }

        return $doc;
    }

    private static function mapsOf(stdClass $phase): void
    {
        foreach (self::MAP_KEYS as $key) {
            if (isset($phase->{$key}) && $phase->{$key} === []) {
                $phase->{$key} = new stdClass;
            }
        }
    }

    /**
     * `$new` with every number that equals the number at the same place in
     * `$old` given `$old`'s type, so a document that went through JavaScript
     * (where 12.0 is 12) keeps `12.0` where it was not changed.
     */
    public static function keepNumberTypes(mixed $new, mixed $old): mixed
    {
        if (is_int($new) && is_float($old) && (float) $new === $old) {
            return $old;
        }
        if ($new instanceof stdClass && $old instanceof stdClass) {
            foreach (get_object_vars($new) as $key => $value) {
                if (property_exists($old, (string) $key)) {
                    $new->{$key} = self::keepNumberTypes($value, $old->{$key});
                }
            }

            return $new;
        }
        if (is_array($new) && is_array($old)) {
            foreach ($new as $i => $value) {
                if (array_key_exists($i, $old)) {
                    $new[$i] = self::keepNumberTypes($value, $old[$i]);
                }
            }
        }

        return $new;
    }

    /**
     * The authored document behind a stored one: a copy without the ids sync
     * resolved (`chronicle.chronicle_id`, `steps[].entry_id`, and the
     * `entity_id` beside every linked reference that has a Q-id or resolved to
     * nothing). An `entity_id` given without a Q-id is the author's and stays.
     */
    public static function authored(stdClass $stored): stdClass
    {
        $doc = self::copy($stored);

        self::stripRef($doc->entity ?? null);
        if (($doc->chronicle ?? null) instanceof stdClass) {
            unset($doc->chronicle->chronicle_id);
        }
        foreach (self::listOf($doc->sides ?? null) as $side) {
            self::stripRef($side->polity ?? null);
            foreach (self::listOf($side->commanders ?? null) as $commander) {
                self::stripRef($commander);
            }
        }
        foreach (self::listOf($doc->units ?? null) as $unit) {
            self::stripRef($unit);
        }
        foreach (self::listOf($doc->features ?? $doc->terrain ?? null) as $feature) {
            self::stripRef($feature->entity ?? null);
        }
        foreach (self::listOf($doc->steps ?? null) as $step) {
            unset($step->entry_id);
            foreach (self::listOf($step->entities ?? null) as $entity) {
                self::stripRef($entity);
            }
            $states = $step->features ?? $step->terrain_state ?? null;
            if ($states instanceof stdClass) {
                foreach (get_object_vars($states) as $state) {
                    if ($state instanceof stdClass) {
                        self::stripRef($state->area_from_entity ?? null);
                    }
                }
            }
        }

        return $doc;
    }

    private static function stripRef(mixed $ref): void
    {
        if (! $ref instanceof stdClass || ! property_exists($ref, 'entity_id')) {
            return;
        }
        if (is_string($ref->wikidata ?? null) || $ref->entity_id === null) {
            unset($ref->entity_id);
        }
    }

    /** @return list<stdClass> the objects in a list (anything else: none) */
    private static function listOf(mixed $value): array
    {
        return is_array($value) ? array_values(array_filter($value, fn (mixed $item) => $item instanceof stdClass)) : [];
    }
}
