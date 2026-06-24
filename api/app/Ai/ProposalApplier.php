<?php

namespace App\Ai;

use App\Models\Ai\ProposedChangePart;
use RuntimeException;

class ProposalApplier
{
    public function __construct(private ToolRegistry $registry) {}

    public function applyPart(ProposedChangePart $part): ProposedChangePart
    {
        if ($part->status === 'applied') {
            return $part;
        }

        $resolved = [];
        if ($part->depends_on) {
            $dep = $part->change->parts()->where('key', $part->depends_on)->first();
            if (! $dep || $dep->status !== 'applied') {
                throw new RuntimeException("Cannot apply: depends_on '{$part->depends_on}' is not applied yet.");
            }
            $resolved['depends'] = $dep->result_id;
        }

        $result = $this->registry->resolve($part->tool)->applyPart($part->payload, $resolved);
        $part->applyApplied($result['result_id']);

        return $part->fresh();
    }
}
