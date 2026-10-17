<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\Entity\FetchEntityImagesAction;
use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\UpdateEntityImagesRequest;
use App\Models\Entity;
use App\Services\WikimediaImages;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;
use RuntimeException;

/**
 * The entity editor's Images panel: the linked images, candidates from a
 * chosen source, and saving the admin's pick. Images stay on Wikimedia (or
 * wherever the URL points); only links and credits are stored.
 */
class EntityImageController extends Controller
{
    public function __construct(private readonly WikimediaImages $wikimedia) {}

    public function index(Entity $entity): JsonResponse
    {
        $attributes = $entity->attributes ?? [];

        return response()->json([
            'data' => is_array($attributes['media_refs'] ?? null) ? array_values($attributes['media_refs']) : [],
            'curated_at' => $attributes[FetchEntityImagesAction::CURATED_KEY] ?? null,
            'wikidata_id' => $entity->wikidata_id,
            'name' => $entity->name,
        ]);
    }

    /**
     * Candidate images from one source:
     *  - wikidata:  every image claim of the entity's item (or of `q`, a QID)
     *  - wikipedia: lead images of English Wikipedia articles matching `q`
     *  - commons:   Commons files matching `q`
     *  - url:       a pasted Commons/Wikipedia file URL, or any other https image
     * `q` defaults to the entity's name (its QID for `wikidata`).
     */
    public function candidates(Request $request, Entity $entity): JsonResponse
    {
        $validated = $request->validate([
            'source' => ['required', Rule::in(['wikidata', 'wikipedia', 'commons', 'url'])],
            'q' => ['nullable', 'string', 'max:2048'],
        ]);
        $source = $validated['source'];
        $q = trim((string) ($validated['q'] ?? ''));

        try {
            $data = match ($source) {
                'wikidata' => $this->fromWikidata($q !== '' ? strtoupper($q) : (string) $entity->wikidata_id),
                'wikipedia' => $this->fromWikipedia($q !== '' ? $q : $entity->name),
                'commons' => array_map(
                    fn (array $info) => WikimediaImages::item($info, 'image', 'commons'),
                    $this->wikimedia->searchCommons($q !== '' ? $q : $entity->name),
                ),
                'url' => $this->fromUrl($q),
            };
        } catch (RuntimeException $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }

        return response()->json(['data' => $data]);
    }

    public function update(UpdateEntityImagesRequest $request, Entity $entity): JsonResponse
    {
        $images = $request->validated('images');

        $files = [];
        foreach ($images as $i => $image) {
            $file = isset($image['file']) ? $image['file'] : WikimediaImages::fileFromUrl((string) ($image['url'] ?? ''));
            if ($file !== null) {
                $files[$i] = $file;
            } elseif (blank($image['license'] ?? null)) {
                throw ValidationException::withMessages([
                    "images.{$i}.license" => 'Give the license for an image that is not on Wikimedia Commons.',
                ]);
            }
        }

        try {
            $info = $files === [] ? [] : $this->wikimedia->fileInfo(array_values($files));
        } catch (RuntimeException $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }

        $items = [];
        foreach ($images as $i => $image) {
            if (isset($files[$i])) {
                $found = $info[$files[$i]] ?? null;
                if ($found === null) {
                    throw ValidationException::withMessages([
                        "images.{$i}.file" => "\"{$files[$i]}\" is not a freely licensed image on Wikimedia Commons.",
                    ]);
                }

                $item = WikimediaImages::item($found, $image['kind'], $image['source'] ?? 'commons', $image['property'] ?? null);
                if (filled($image['caption'] ?? null)) {
                    $item['caption'] = $image['caption'];
                }
            } else {
                $item = array_filter([
                    'type' => 'image',
                    'kind' => $image['kind'],
                    'url' => $image['url'],
                    'page_url' => $image['page_url'] ?? $image['url'],
                    'caption' => $image['caption'] ?? null,
                    'author' => $image['author'] ?? null,
                    'license' => $image['license'],
                    'license_url' => $image['license_url'] ?? null,
                    'source' => 'external',
                    'fetched_at' => now()->toIso8601String(),
                ], fn ($v) => $v !== null);
            }

            $items[] = $item;
        }

        // Merge into attributes in SQL so a concurrent edit of other keys survives.
        DB::update(
            "UPDATE entities SET attributes = (CASE WHEN jsonb_typeof(attributes) = 'object' THEN attributes ELSE '{}'::jsonb END) || jsonb_build_object('media_refs', ?::jsonb, ?::text, ?::text), updated_at = now() WHERE entity_id = ?",
            [
                json_encode($items, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
                FetchEntityImagesAction::CURATED_KEY,
                now()->toIso8601String(),
                $entity->entity_id,
            ],
        );

        return $this->index($entity->refresh());
    }

    /** @return list<array<string, mixed>> */
    private function fromWikidata(string $qid): array
    {
        if (! preg_match('/^Q\d+$/', $qid)) {
            return [];
        }

        $files = $this->wikimedia->wikidataFiles([$qid])[$qid]['files'] ?? [];
        $info = $this->wikimedia->fileInfo(array_merge([], ...array_values($files)));

        $items = [];
        foreach ($files as $property => $names) {
            foreach ($names as $name) {
                if (isset($info[$name])) {
                    $items[] = WikimediaImages::item($info[$name], WikimediaImages::PROPERTIES[$property], 'wikidata', $property);
                }
            }
        }

        return $items;
    }

    /** @return list<array<string, mixed>> */
    private function fromWikipedia(string $query): array
    {
        $articles = $this->wikimedia->searchWikipedia($query);
        $info = $this->wikimedia->fileInfo(array_column($articles, 'file'));

        $items = [];
        foreach ($articles as $article) {
            if (isset($info[$article['file']]) && ! in_array($article['file'], array_column($items, 'file'), true)) {
                $items[] = [...WikimediaImages::item($info[$article['file']], 'image', 'wikipedia'), 'found_on' => $article['title']];
            }
        }

        return $items;
    }

    /** @return list<array<string, mixed>> */
    private function fromUrl(string $url): array
    {
        if (! filter_var($url, FILTER_VALIDATE_URL) || ! str_starts_with($url, 'https://')) {
            throw ValidationException::withMessages(['q' => 'Paste an https link to an image or a Commons file page.']);
        }

        $file = WikimediaImages::fileFromUrl($url);
        if ($file === null) {
            // Not Wikimedia: the admin types the credit before saving.
            return [['type' => 'image', 'kind' => 'image', 'url' => $url, 'page_url' => $url, 'source' => 'external']];
        }

        $info = $this->wikimedia->fileInfo([$file])[$file] ?? null;
        if ($info === null) {
            throw ValidationException::withMessages(['q' => "\"{$file}\" is not a freely licensed image on Wikimedia Commons."]);
        }

        return [WikimediaImages::item($info, 'image', 'commons')];
    }
}
