<?php

namespace App\Models\Ai;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ProposedChangePart extends Model
{
    use HasUuids;

    protected $table = 'agent_proposed_change_parts';

    protected $fillable = ['change_id', 'key', 'tool', 'payload', 'human_diff', 'status', 'depends_on', 'result_id', 'applied_at'];

    protected $casts = ['payload' => 'array', 'human_diff' => 'array', 'applied_at' => 'datetime'];

    public function change(): BelongsTo
    {
        return $this->belongsTo(ProposedChange::class, 'change_id');
    }

    public function applyApplied(string $resultId): void
    {
        $this->update(['status' => 'applied', 'result_id' => $resultId, 'applied_at' => now()]);
    }

    public function markDiscarded(): void
    {
        $this->update(['status' => 'discarded']);
    }
}
