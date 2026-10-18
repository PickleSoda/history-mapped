<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleFormat;
use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\RecordType;
use App\Support\ContentBundle\Schemas;

/**
 * The package layer: which files exist, whether their names are safe, and whether the manifest is valid
 * and its `_base/` checksums still match. Missing record files are fine (partial bundles drop files).
 */
final class PackageChecks implements ValidationLayer
{
    public function name(): string
    {
        return Issue::PACKAGE;
    }

    public function run(BundleReader $bundle, IssueSink $sink, bool $againstSite = false): void
    {
        $this->files($bundle, $sink);
        $manifest = $this->manifest($bundle, $sink);
        if ($manifest !== null) {
            $this->checksums($bundle, $sink, $manifest);
        }
    }

    private function files(BundleReader $bundle, IssueSink $sink): void
    {
        foreach ($bundle->duplicates() as $name) {
            $sink->add(Issue::error(Issue::PACKAGE, 'duplicate zip entry '.self::printable($name).': tools disagree on which copy is read'));
        }

        $allowed = [BundleFormat::MANIFEST => 1, BundleFormat::LICENSE => 1];
        foreach (RecordType::cases() as $type) {
            $allowed[$type->file()] = 1;
            $allowed[BundleFormat::BASE_DIR.'/'.$type->file()] = 1;
        }
        foreach ($bundle->files() as $name) {
            if (BundleFormat::isUnsafePath($name)) {
                $sink->add(Issue::error(Issue::PACKAGE, 'unsafe file name', self::printable($name)));
            } elseif (! isset($allowed[$name])) {
                $sink->add(Issue::error(Issue::PACKAGE, 'unknown file; a bundle holds only manifest.json, LICENSE.md, the record files and _base/', $name));
            }
        }
    }

    /** @return \stdClass|null the manifest when it could be read */
    private function manifest(BundleReader $bundle, IssueSink $sink): ?\stdClass
    {
        $file = BundleFormat::MANIFEST;
        if (! $bundle->has($file)) {
            $sink->add(Issue::error(Issue::PACKAGE, 'manifest.json is missing', $file));

            return null;
        }
        $manifest = $bundle->manifestObject();
        if ($manifest === null) {
            $sink->add(Issue::error(Issue::PACKAGE, 'cannot read manifest: '.($bundle->manifestError() ?? 'unknown error'), $file));

            return null;
        }

        $result = Schemas::validator()->validate($manifest, Schemas::manifestSchemaId());
        if (! $result->isValid()) {
            foreach (SchemaIssues::map($result->error(), Issue::PACKAGE, $file, null, null) as $issue) {
                $sink->add($issue);
            }
        }

        $version = $manifest->version ?? null;
        if (is_int($version) && $version !== BundleFormat::VERSION) {
            $sink->add(Issue::error(Issue::PACKAGE, "unsupported bundle version {$version}; this site reads version ".BundleFormat::VERSION, $file, null, '/version'));
        }

        return $manifest;
    }

    private function checksums(BundleReader $bundle, IssueSink $sink, \stdClass $manifest): void
    {
        $listed = isset($manifest->checksums) && is_object($manifest->checksums) ? (array) $manifest->checksums : [];
        $prefix = BundleFormat::BASE_DIR.'/';
        foreach ($listed as $name => $expected) {
            $name = (string) $name;
            if (! str_starts_with($name, $prefix) || BundleFormat::isUnsafePath($name) || ! is_string($expected) || ! str_starts_with($expected, 'sha256:')) {
                continue; // the schema layer already flagged it
            }
            if (! $bundle->has($name)) {
                $sink->add(Issue::error(Issue::PACKAGE, 'manifest lists a checksum for a file that is not in the bundle', $name));
            } elseif ($bundle->sha256($name) !== $expected) {
                $sink->add(Issue::error(Issue::PACKAGE, '_base snapshot was modified; re-export instead of editing _base/', $name));
            }
        }
        foreach (RecordType::cases() as $type) {
            $name = $prefix.$type->file();
            if ($bundle->has($name) && ! array_key_exists($name, $listed)) {
                $sink->add(Issue::error(Issue::PACKAGE, 'file is not listed in the manifest checksums', $name));
            }
        }
    }

    private static function printable(string $name): string
    {
        $clean = preg_replace('/[^\x20-\x7e]/', '?', $name) ?? '?';

        return mb_strimwidth($clean, 0, 120, '…');
    }
}
