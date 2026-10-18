<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleLineTooLongException;
use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\RecordType;
use App\Support\ContentBundle\Schemas;

/**
 * The structure layer: every line of every root record file must be a JSON object that satisfies its
 * JSON Schema. Streams line by line; a file with MAX_ERROR_LINES erroneous lines is abandoned to bound the time.
 */
final class StructureChecks
{
    public const MAX_ERROR_LINES = 10_000;

    public function __construct(private readonly int $maxErrorLines = self::MAX_ERROR_LINES) {}

    public function run(BundleReader $bundle, IssueSink $sink): void
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
        $schema = Schemas::recordSchemaId($type);
        $badLines = 0;

        try {
            foreach ($bundle->lines($file) as $n => $line) {
                $id = null;
                $found = [];
                $data = json_decode($line);
                if (json_last_error() !== JSON_ERROR_NONE) {
                    $found[] = Issue::error(Issue::STRUCTURE, 'invalid JSON: '.json_last_error_msg(), $file, $n);
                } elseif (! $data instanceof \stdClass) {
                    $found[] = Issue::error(Issue::STRUCTURE, 'line must be a JSON object', $file, $n);
                } else {
                    $id = isset($data->id) && is_string($data->id) ? $data->id : null;
                    $result = Schemas::validator()->validate($data, $schema);
                    if (! $result->isValid()) {
                        $found = SchemaIssues::map($result->error(), Issue::STRUCTURE, $file, $n, $id);
                    }
                }

                $hash = null;
                $hasError = false;
                foreach ($found as $issue) {
                    $hasError = $sink->add($issue, $hash ??= sha1($line, true)) === Issue::ERROR || $hasError;
                }
                if ($hasError && ++$badLines >= $this->maxErrorLines) {
                    $sink->note($file, "validation of this file stopped after {$this->maxErrorLines} lines with errors");
                    break;
                }
            }
        } catch (BundleLineTooLongException $e) {
            $limit = $e->limit % (1024 * 1024) === 0 ? ($e->limit / (1024 * 1024)).' MB' : $e->limit.' bytes';
            $sink->add(Issue::error(Issue::STRUCTURE, "line is longer than {$limit}", $file, $e->lineNumber));
        }

        if ($bundle->hadByteOrderMark($file)) {
            $sink->add(Issue::warning(Issue::STRUCTURE, 'file starts with a byte-order mark; it was ignored', $file));
        }
        if (($blank = $bundle->blankLineCount($file)) > 0) {
            $sink->add(Issue::warning(Issue::STRUCTURE, "{$blank} blank ".($blank === 1 ? 'line' : 'lines').' ignored', $file));
        }
    }
}
