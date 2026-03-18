<?php

declare(strict_types=1);

namespace App\Actions\Source;

use App\DTOs\SourceData;
use App\Models\Source;

/**
 * Create a new Source record.
 */
class CreateSourceAction
{
    public function __invoke(SourceData $data): Source
    {
        return Source::create($data->toModelArray());
    }
}
