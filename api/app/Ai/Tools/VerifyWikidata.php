<?php

namespace App\Ai\Tools;

use App\Services\WikidataService;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Ai\Tools\Request;
use LogicException;
use Stringable;

class VerifyWikidata extends AgentTool
{
    public function __construct(
        private WikidataService $wikidata,
    ) {}

    public static function name(): string
    {
        return 'verify_wikidata';
    }

    public function description(): string
    {
        return 'Fetch live metadata for a Wikidata QID (label, description, P31 instance-of, coordinates) to verify it matches the entity before linking.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'qid' => $schema->string()->description('Wikidata QID, e.g. Q28567')->required(),
        ];
    }

    /**
     * Read-only: query Wikidata directly, no proposal staged.
     */
    public function handle(Request $request): Stringable|string
    {
        $qid = $request['qid'];
        $meta = $this->wikidata->fetch($qid);

        if ($meta === null) {
            return json_encode(['found' => false, 'qid' => $qid, 'message' => "QID {$qid} not found on Wikidata."], JSON_THROW_ON_ERROR);
        }

        return json_encode(array_merge(['found' => true, 'qid' => $qid], $meta), JSON_THROW_ON_ERROR);
    }

    public function buildParts(array $args): array
    {
        throw new LogicException('VerifyWikidata is a read-only tool — it does not stage proposals.');
    }

    public function applyPart(array $payload, array $resolved): array
    {
        throw new LogicException('VerifyWikidata is a read-only tool — it does not apply parts.');
    }
}
