<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\RecordType;

/**
 * The records layer: per-line rules (RecordRules) plus duplicate detection across a file. Streams each
 * file once and keeps, per duplicate rule, only a map from key to the first line's number and sha1 hash.
 * It runs only when the structure layer found no errors, so every line decodes to an object of the right
 * shape.
 *
 * A duplicate involves two lines, so it is reported on the later one with both hashes: it is downgraded to
 * a warning only when both lines are unchanged since export. Inserting a new duplicate ahead of an old line
 * therefore stays an error.
 *
 * Absent keys read as null on new-record and `replace` lines. A `merge` line is checked only for the rules
 * whose keys are all present; a partial merge is checked against the merged value by the import planner.
 */
final class RecordChecks implements ValidationLayer
{
    private const RELATIONSHIP_KEYS = ['source_entity_id', 'target_entity_id', 'relationship_type', 'start_year', 'end_year'];

    public function name(): string
    {
        return Issue::RECORDS;
    }

    public function run(BundleReader $bundle, IssueSink $sink, bool $againstSite): void
    {
        foreach (RecordType::cases() as $type) {
            if ($bundle->has($type->file())) {
                $this->file($bundle, $sink, $type);
            }
        }
    }

    private function file(BundleReader $bundle, IssueSink $sink, RecordType $type): void
    {
        $file = $type->file();
        /** @var array<string, string> $ids id => first line, packed */
        $ids = [];
        /** @var array<string, string> $unique relationship key, chronicle slug or wikidata id => first line, packed */
        $unique = [];

        foreach ($bundle->lines($file) as $n => $line) {
            $d = json_decode($line, false);
            if (! $d instanceof \stdClass) {
                continue;
            }
            $id = isset($d->id) && is_string($d->id) ? $d->id : null;
            $op = $d->_op ?? null;
            $hash = sha1($line, true);
            /** @var list<array{string, string, string, ?string}> $problems severity, message, field, first line's pack */
            $problems = [];

            if ($id !== null) {
                $this->seen($ids, $id, $n, $hash, 'duplicate id', '/id', Issue::ERROR, $problems);
            }

            if ($op !== 'delete') {
                $this->duplicates($type, $d, $n, $hash, $id === null || $op === 'replace', $unique, $problems);
                foreach (RecordRules::check($type, $d, $id === null || $op === 'replace') as $v) {
                    $problems[] = [$v->severity, $v->message, $v->field, null];
                }
            }

            foreach ($problems as [$severity, $message, $field, $first]) {
                $issue = $severity === Issue::ERROR
                    ? Issue::error(Issue::RECORDS, $message, $file, $n, $field, $id)
                    : Issue::warning(Issue::RECORDS, $message, $file, $n, $field, $id);
                $first === null ? $sink->add($issue, $hash) : $sink->add($issue, $hash, substr($first, 4));
            }
        }
    }

    /**
     * Records `$key` as seen at line `$n`, or adds a problem naming the first line when it was seen before.
     *
     * @param  array<string, string>  $seen
     * @param  list<array{string, string, string, ?string}>  $problems
     */
    private function seen(array &$seen, string $key, int $n, string $hash, string $what, string $field, string $severity, array &$problems): void
    {
        if (isset($seen[$key])) {
            $first = unpack('N', $seen[$key])[1];
            $problems[] = [$severity, "{$what}: also on line {$first}", $field, $seen[$key]];
        } else {
            $seen[$key] = pack('N', $n).$hash;
        }
    }

    /**
     * @param  array<string, string>  $unique
     * @param  list<array{string, string, string, ?string}>  $problems
     */
    private function duplicates(RecordType $type, \stdClass $d, int $n, string $hash, bool $complete, array &$unique, array &$problems): void
    {
        if ($type === RecordType::Relationships) {
            // A merge line must carry every key to be comparable; otherwise the planner checks the merged value.
            $present = array_filter(self::RELATIONSHIP_KEYS, fn ($k) => property_exists($d, $k));
            if (! $complete && count($present) < count(self::RELATIONSHIP_KEYS)) {
                return;
            }
            foreach (['source_entity_id', 'target_entity_id', 'relationship_type'] as $k) {
                if (! isset($d->$k) || ! is_string($d->$k)) {
                    return;
                }
            }
            $key = sha1(implode("\0", [$d->source_entity_id, $d->target_entity_id, $d->relationship_type, (string) ($d->start_year ?? ''), (string) ($d->end_year ?? '')]), true);
            $this->seen($unique, $key, $n, $hash, 'duplicate relationship', '/relationship_type', Issue::ERROR, $problems);
        } elseif ($type === RecordType::Chronicles && isset($d->slug) && is_string($d->slug)) {
            $this->seen($unique, $d->slug, $n, $hash, "duplicate chronicle slug \"{$d->slug}\"", '/slug', Issue::ERROR, $problems);
        } elseif ($type === RecordType::Entities && isset($d->wikidata_id) && is_string($d->wikidata_id)) {
            $this->seen($unique, $d->wikidata_id, $n, $hash, "duplicate wikidata_id {$d->wikidata_id}", '/wikidata_id', Issue::WARNING, $problems);
        }
    }
}
