<?php

namespace App\Models\Ai;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class ProposedChange extends Model
{
    use HasUuids;

    protected $table = 'agent_proposed_changes';

    protected $fillable = ['user_id', 'conversation_id', 'context_type', 'context_id'];

    public function parts(): HasMany
    {
        return $this->hasMany(ProposedChangePart::class, 'change_id');
    }
}
