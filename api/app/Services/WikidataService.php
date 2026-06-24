<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;

class WikidataService
{
    public function fetch(string $qid): ?array
    {
        $res = Http::acceptJson()->get("https://www.wikidata.org/wiki/Special:EntityData/{$qid}.json");
        $entity = $res->json("entities.{$qid}");
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
