<?php

declare(strict_types=1);

namespace App\Actions\Contribution;

use App\Enums\ContributionKind;
use App\Enums\ContributionSource;
use App\Enums\ContributionStatus;
use App\Enums\ContributionTargetType;
use App\Enums\EntityType;
use App\Exceptions\EntityQidExistsException;
use App\Exceptions\PossibleDuplicatesException;
use App\Models\Contribution;
use App\Models\Entity;
use App\Models\User;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;

/**
 * Record a proposal for a new entity. Nothing is created: the validated
 * payload is held as a `create` contribution until a moderator approves it
 * (ApproveProposalAction -> CreateEntityAction).
 *
 * Input keys follow StoreEntityRequest (snake_case); a narrower set, since a
 * contributor proposes facts, not editorial state. Guards, in order:
 *  - validation (like StoreEntityRequest, plus the year format the date
 *    trigger can parse and end >= start);
 *  - the per-account pending cap shared with SubmitContributionAction;
 *  - a Wikidata QID the atlas already has (or that is already proposed and
 *    waiting) is refused;
 *  - same-name, same-type entities within DUPLICATE_YEARS of the proposed
 *    start (or with no dates) stop the proposal with PossibleDuplicatesException
 *    unless `$acknowledgeDuplicates` says the caller has seen them.
 */
class ProposeEntityAction
{
    /** Years either side of the proposed start in which a same-name entity counts as a possible duplicate. */
    public const DUPLICATE_YEARS = 50;

    /** Most possible duplicates listed. */
    public const MAX_DUPLICATES = 5;

    /** Atlas year bounds, as in the content-bundle contract. */
    public const MIN_YEAR = -20000;

    public const MAX_YEAR = 3000;

    /**
     * @param  array<string, mixed>  $input
     *
     * @throws ValidationException
     * @throws EntityQidExistsException
     * @throws PossibleDuplicatesException
     */
    public function __invoke(
        User $user,
        array $input,
        ?string $note = null,
        bool $acknowledgeDuplicates = false,
        ContributionSource $source = ContributionSource::Atlas,
        ?string $client = null,
    ): Contribution {
        $data = $this->validate($input);

        $pending = $user->contributions()->where('status', ContributionStatus::Pending)->count();
        if ($pending >= SubmitContributionAction::MAX_PENDING_PER_USER) {
            throw ValidationException::withMessages([
                'name' => 'You have too many proposals awaiting review. Please wait for some to be reviewed.',
            ]);
        }

        if (isset($data['wikidata_id'])) {
            $this->guardQid($data['wikidata_id']);
        }

        $duplicates = $this->possibleDuplicates($data);
        if ($duplicates !== [] && ! $acknowledgeDuplicates) {
            throw new PossibleDuplicatesException($duplicates);
        }

        return $user->contributions()->create([
            'kind' => ContributionKind::Create,
            'target_type' => ContributionTargetType::Entity,
            'payload' => ['entity' => $data, 'possible_duplicates' => $duplicates],
            'note' => $note === null || trim($note) === '' ? null : trim($note),
            'status' => ContributionStatus::Pending,
            'source' => $source,
            'client' => $client,
        ]);
    }

    /**
     * @param  array<string, mixed>  $input
     * @return array<string, mixed>
     */
    private function validate(array $input): array
    {
        $year = ['nullable', 'string', 'max:50', 'regex:/^-?\d{1,5}(-\d{2}(-\d{2})?)?$/'];

        $data = Validator::make($input, [
            'name' => ['required', 'string', 'min:2', 'max:500'],
            'entity_type' => ['required', 'string', Rule::enum(EntityType::class)],
            'summary' => ['nullable', 'string', 'max:5000'],
            'description' => ['nullable', 'string', 'max:20000'],
            'alternative_names' => ['nullable', 'array', 'max:20'],
            'alternative_names.*' => ['string', 'max:500'],
            'wikidata_id' => ['nullable', 'string', 'regex:/^Q\d+$/'],
            'temporal_start' => $year,
            'temporal_end' => $year,
            'location_name' => ['nullable', 'string', 'max:500'],
            'geojson' => ['nullable', 'array'],
            'geojson.type' => ['required_with:geojson', 'string', Rule::in(['Point'])],
            'geojson.coordinates' => ['required_with:geojson', 'array', 'size:2'],
            'geojson.coordinates.0' => ['numeric', 'between:-180,180'],
            'geojson.coordinates.1' => ['numeric', 'between:-90,90'],
            'source_citations' => ['nullable', 'array', 'max:10'],
            'source_citations.*.title' => ['nullable', 'string', 'max:300'],
            'source_citations.*.url' => ['nullable', 'url:http,https', 'max:1000'],
        ])->after(function ($v) use ($input): void {
            $start = self::leadingYear($input['temporal_start'] ?? null);
            $end = self::leadingYear($input['temporal_end'] ?? null);
            foreach (['temporal_start' => $start, 'temporal_end' => $end] as $key => $y) {
                if ($y !== null && ($y < self::MIN_YEAR || $y > self::MAX_YEAR || $y === 0)) {
                    $v->errors()->add($key, 'The year must be between '.self::MIN_YEAR.' and '.self::MAX_YEAR.', with no year 0 (use -1 for 1 BC).');
                }
            }
            if ($start !== null && $end !== null && $end < $start) {
                $v->errors()->add('temporal_end', 'The end cannot be before the start.');
            }
            foreach ((array) ($input['source_citations'] ?? []) as $i => $c) {
                if (is_array($c) && blank($c['title'] ?? null) && blank($c['url'] ?? null)) {
                    $v->errors()->add("source_citations.$i", 'A source needs a title or a url.');
                }
            }
        })->validate();

        $type = EntityType::from($data['entity_type']);
        $out = [
            'name' => trim($data['name']),
            'entity_type' => $type->value,
            'entity_group' => $type->group()->value,
        ];
        foreach (['summary', 'description', 'wikidata_id', 'temporal_start', 'temporal_end', 'location_name', 'geojson'] as $key) {
            if (! blank($data[$key] ?? null)) {
                $out[$key] = is_string($data[$key]) ? trim($data[$key]) : $data[$key];
            }
        }
        if (isset($out['geojson'])) {
            $out['geojson'] = [
                'type' => 'Point',
                'coordinates' => [(float) $out['geojson']['coordinates'][0], (float) $out['geojson']['coordinates'][1]],
            ];
        }
        $aliases = array_values(array_unique(array_filter(
            array_map('trim', (array) ($data['alternative_names'] ?? [])),
            fn (string $a): bool => $a !== '' && mb_strtolower($a) !== mb_strtolower($out['name']),
        )));
        if ($aliases !== []) {
            $out['alternative_names'] = $aliases;
        }
        $citations = [];
        foreach ((array) ($data['source_citations'] ?? []) as $c) {
            $citations[] = array_filter([
                'source_type' => 'reference',
                'title' => isset($c['title']) ? trim((string) $c['title']) : null,
                'url' => $c['url'] ?? null,
            ], fn ($v) => $v !== null && $v !== '');
        }
        if ($citations !== []) {
            $out['source_citations'] = $citations;
        }

        return $out;
    }

    private function guardQid(string $qid): void
    {
        $existing = Entity::query()->where('wikidata_id', $qid)->first(['entity_id', 'name', 'wikidata_id']);
        if ($existing !== null) {
            throw new EntityQidExistsException($existing);
        }

        $proposed = Contribution::query()
            ->where('kind', ContributionKind::Create)
            ->where('target_type', ContributionTargetType::Entity)
            ->where('status', ContributionStatus::Pending)
            ->whereRaw("payload->'entity'->>'wikidata_id' = ?", [$qid])
            ->exists();
        if ($proposed) {
            throw ValidationException::withMessages(['wikidata_id' => "{$qid} has already been proposed and is awaiting review."]);
        }
    }

    /**
     * Same name (case-insensitive) and type; when a start year is given, within
     * DUPLICATE_YEARS of it, or undated (an undated twin cannot be ruled out).
     *
     * @param  array<string, mixed>  $data
     * @return list<array{entity_id: string, name: string, entity_type: string, start_year: int|null, end_year: int|null}>
     */
    private function possibleDuplicates(array $data): array
    {
        $start = self::leadingYear($data['temporal_start'] ?? null);

        $query = Entity::query()
            ->leftJoin('entity_temporal_ranges as r', fn ($j) => $j->on('r.entity_id', '=', 'entities.entity_id')->where('r.is_primary', true))
            ->whereRaw('lower(entities.name) = ?', [mb_strtolower($data['name'])])
            ->where('entities.entity_type', $data['entity_type'])
            ->orderBy('entities.name')
            ->limit(self::MAX_DUPLICATES)
            ->select(['entities.entity_id', 'entities.name', 'entities.entity_type', 'r.start_year', 'r.end_year']);
        if ($start !== null) {
            $query->where(fn ($q) => $q
                ->whereNull('r.start_year')
                ->orWhereBetween('r.start_year', [$start - self::DUPLICATE_YEARS, $start + self::DUPLICATE_YEARS]));
        }

        return $query->toBase()->get()->map(fn ($row) => [
            'entity_id' => $row->entity_id,
            'name' => $row->name,
            'entity_type' => $row->entity_type,
            'start_year' => $row->start_year === null ? null : (int) $row->start_year,
            'end_year' => $row->end_year === null ? null : (int) $row->end_year,
        ])->all();
    }

    /** The leading signed integer of a date string ("-0480-08" gives -480), or null. */
    public static function leadingYear(mixed $value): ?int
    {
        return is_string($value) && preg_match('/^-?\d+/', $value, $m) === 1 ? (int) $m[0] : null;
    }
}
