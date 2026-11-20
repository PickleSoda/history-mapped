{{-- A chronicle page as text: what the web app's /chronicles/{slug} shows, for
     readers that run no JavaScript. --}}
<article id="hm-static">
<p class="hm-meta"><a href="/browse">Browse</a></p>
<h1>{{ $chronicle->title }}</h1>
<p class="hm-meta">{{ implode(' · ', array_filter(['Chronicle', count($steps).' '.(count($steps) === 1 ? 'step' : 'steps'), $span])) }}</p>
@foreach (\App\Services\Site\SiteText::paragraphs($chronicle->description) as $paragraph)
<p>{{ $paragraph }}</p>
@endforeach
@foreach ($steps as $i => $step)
<h2>{{ $i + 1 }}. {{ $step['span'] ?? 'Step '.($i + 1) }}</h2>
@foreach ($step['paragraphs'] as $paragraph)
<p>{{ $paragraph }}</p>
@endforeach
@if ($step['entities'] !== [])
<p class="hm-meta">@foreach ($step['entities'] as $entity)<a href="/entities/{{ $entity['id'] }}">{{ $entity['name'] }}</a>@if (! $loop->last), @endif @endforeach</p>
@endif
@endforeach
<p class="hm-meta"><a href="/app?chron={{ rawurlencode($chronicle->slug) }}">Open on the globe</a></p>
</article>