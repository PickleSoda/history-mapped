{{-- An entity page as text: what the web app's /entities/{id} shows, for readers
     that run no JavaScript. Section names follow the app's entity page. --}}
<article id="hm-static">
<p class="hm-meta"><a href="/browse">Browse</a></p>
<h1>{{ $entity->name }}</h1>
<p class="hm-meta">{{ implode(' · ', array_filter([$typeLabel, $span, $place])) }}</p>
@if ($aliases !== [])
<p>Also known as: {{ implode(', ', $aliases) }}</p>
@endif
@foreach (\App\Services\Site\SiteText::paragraphs($entity->summary) as $paragraph)
<p>{{ $paragraph }}</p>
@endforeach
@if (trim((string) $entity->significance) !== '')
<h2>Significance</h2>
@foreach (\App\Services\Site\SiteText::paragraphs($entity->significance) as $paragraph)
<p>{{ $paragraph }}</p>
@endforeach
@endif
@if (trim((string) $entity->description) !== '')
<h2>About</h2>
@foreach (\App\Services\Site\SiteText::paragraphs($entity->description) as $paragraph)
<p>{{ $paragraph }}</p>
@endforeach
@endif
@if ($connections !== [])
<h2>Connections</h2>
<ul>
@foreach ($connections as $c)
<li>{{ ucfirst($c['label']) }} <a href="/entities/{{ $c['id'] }}">{{ $c['name'] }}</a>@if ($c['type'] !== null || $c['span'] !== null) ({{ implode(', ', array_filter([$c['type'], $c['span']])) }})@endif</li>
@endforeach
</ul>
@endif
@if ($chronicles->isNotEmpty())
<h2>In chronicles</h2>
<ul>
@foreach ($chronicles as $chronicle)
<li><a href="/chronicles/{{ rawurlencode($chronicle->slug) }}">{{ $chronicle->title }}</a></li>
@endforeach
</ul>
@endif
<p class="hm-meta"><a href="/app?sel={{ $entity->entity_id }}&amp;full=1">Open on the globe</a>@if ($entity->wikidata_id) · <a href="https://www.wikidata.org/wiki/{{ $entity->wikidata_id }}" rel="noopener">Wikidata {{ $entity->wikidata_id }}</a>@endif</p>
</article>