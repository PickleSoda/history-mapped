<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;

#[Fillable([
    'chronicle_id', 'title', 'slug', 'source_type', 'source_reference',
    'status', 'start_year', 'end_year', 'impact_score', 'approximate_location', 'metadata', 'created_by', 'created_at', 'updated_at',
])]
class Chronicle extends Model
{
    use HasFactory;

    protected $table = 'chronicles';

    protected $primaryKey = 'chronicle_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected function casts(): array
    {
        return [
            'status' => ChronicleStatus::class,
            'source_type' => SourceType::class,
            'start_year' => 'integer',
            'end_year' => 'integer',
            'impact_score' => 'integer',
            'approximate_location' => 'json',
            'metadata' => 'json',
        ];
    }

    /**
     * The raw `chronicle_tags` rows (with `source`), for the content-bundle export.
     *
     * @return HasMany<ChronicleTag, $this>
     */
    public function tagRows(): HasMany
    {
        return $this->hasMany(ChronicleTag::class, 'chronicle_id', 'chronicle_id');
    }

    /** @return HasMany<ChronicleEntry, $this> */
    public function entries(): HasMany
    {
        return $this->hasMany(ChronicleEntry::class, 'chronicle_id', 'chronicle_id')
            ->orderBy('sequence_order');
    }

    /**
     * Only chronicles carrying the given tags (see Tag::filterGroups()).
     *
     * @param  Builder<Chronicle>  $query
     * @param  list<string>  $slugs
     */
    public function scopeWithTags(Builder $query, array $slugs): void
    {
        $groups = Tag::filterGroups($slugs);
        if ($groups === null) {
            $query->whereRaw('false');

            return;
        }

        foreach ($groups as $group) {
            $query->whereExists(fn ($sub) => $sub->selectRaw('1')
                ->from('chronicle_tags as ctf')
                ->whereColumn('ctf.chronicle_id', 'chronicles.chronicle_id')
                ->whereIn('ctf.tag', $group));
        }
    }

    /**
     * Tags (slug-keyed), including implied ancestors. Ordered by facet, then
     * vocabulary order.
     *
     * @return BelongsToMany<Tag, $this>
     */
    public function tags(): BelongsToMany
    {
        return $this->belongsToMany(Tag::class, 'chronicle_tags', 'chronicle_id', 'tag', 'chronicle_id', 'slug')
            ->withPivot('source')
            ->withTimestamps()
            ->ordered();
    }
}
