<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleReader;

/**
 * One validation layer. BundleValidator runs the layers in order and stops after the first one whose
 * name() has errors, so a layer may assume every earlier layer passed. Layers report through the sink and
 * let bundle read failures propagate; the validator turns those into package errors.
 */
interface ValidationLayer
{
    /** The Issue layer constant this layer's issues carry. */
    public function name(): string;

    public function run(BundleReader $bundle, IssueSink $sink, bool $againstSite): void;
}
