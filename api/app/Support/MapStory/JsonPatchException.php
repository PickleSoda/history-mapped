<?php

declare(strict_types=1);

namespace App\Support\MapStory;

use RuntimeException;

/** A JSON Patch operation that cannot apply; the message names it. */
final class JsonPatchException extends RuntimeException {}
