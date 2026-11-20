{{-- Head tags the app writes into the SPA shell for one page (SiteShell::render). --}}
<title>{{ $title }}</title>
    <meta name="description" content="{{ $page->description }}">
@if ($page->index)
    <link rel="canonical" href="{{ $url }}">
    <meta property="og:url" content="{{ $url }}">
@else
    <meta name="robots" content="noindex">
@endif
    <meta property="og:site_name" content="{{ $siteName }}">
    <meta property="og:type" content="article">
    <meta property="og:title" content="{{ $page->title }}">
    <meta property="og:description" content="{{ $page->description }}">
@if ($page->image !== null)
    <meta property="og:image" content="{{ $page->image }}">
@endif
    <meta name="twitter:card" content="summary">
@if ($jsonLd !== null)
    <script type="application/ld+json">{!! $jsonLd !!}</script>
@endif
    {{-- The text below sits in the root element until the application starts. --}}
    <style>
      #hm-static{max-width:46rem;margin:0 auto;padding:4.5rem 1.25rem 3rem;line-height:1.6}
      #hm-static h1{font-size:1.9rem;line-height:1.2;font-weight:600;margin:0 0 .35rem}
      #hm-static h2{font-size:1.15rem;font-weight:600;margin:1.75rem 0 .5rem}
      #hm-static p{margin:.5rem 0}
      #hm-static ul,#hm-static ol{margin:.5rem 0;padding-left:1.25rem;list-style:disc}
      #hm-static a{text-decoration:underline}
      #hm-static .hm-meta{opacity:.7}
    </style>
