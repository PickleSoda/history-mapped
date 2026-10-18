<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleReader;

/** A layer that checks nothing; the stand-in for a layer that is not built yet. */
final class NoChecks implements ValidationLayer
{
    public function __construct(private readonly string $name) {}

    public function name(): string
    {
        return $this->name;
    }

    public function run(BundleReader $bundle, IssueSink $sink, bool $againstSite): void {}
}
