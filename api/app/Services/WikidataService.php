<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;

class WikidataService
{
    public function fetch(string $qid): ?array
    {
        // Wikidata always keys the JSON under the canonical uppercase QID, so a
        // lowercase/padded id (or a merged id that redirects to a new QID) won't
        // match a naive entities.{$qid} lookup. Normalise, then fall back to the
        // single entity the API actually returned.
        $qid = strtoupper(trim($qid));

        // Wikimedia rejects requests without a descriptive User-Agent with a 403
        // (policy https://w.wiki/4wJS, phabricator T400119), which would make
        // every QID look "not found". Mirror the pipeline's WIKIDATA_USER_AGENT.
        $userAgent = env('WIKIDATA_USER_AGENT', 'history-mapped/1.0 (https://github.com/PickleSoda/history-mapped)');

        $res = Http::acceptJson()
            ->withUserAgent($userAgent)
            ->get("https://www.wikidata.org/wiki/Special:EntityData/{$qid}.json");
        $entities = $res->json('entities');
        if (! is_array($entities)) {
            return null;
        }

        $entity = $entities[$qid] ?? (count($entities) === 1 ? reset($entities) : null);
        if (! is_array($entity)) {
            return null;
        }

        $claims = $entity['claims'] ?? [];
        $coordVal = data_get($claims, 'P625.0.mainsnak.datavalue.value');

        return [
            'label' => data_get($entity, 'labels.en.value'),
            'description' => data_get($entity, 'descriptions.en.value'),
            'p31' => collect($claims['P31'] ?? [])
                ->map(fn ($c) => data_get($c, 'mainsnak.datavalue.value.id'))
                ->filter()->values()->all(),
            'coord' => $coordVal ? ['lon' => $coordVal['longitude'], 'lat' => $coordVal['latitude']] : null,
        ];
    }
}
