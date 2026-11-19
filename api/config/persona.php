<?php

/*
|--------------------------------------------------------------------------
| "Talk with people" (spec 2026-11-19)
|--------------------------------------------------------------------------
|
| A signed-in user chats with a historical person, who answers in character
| from atlas data only. Everything tunable lives here; `.env` keys are named
| in each comment.
*/

return [

    // A person can be talked to only when they died at least this many years
    // ago (PERSONA_MIN_YEARS_DEAD). No living or recently dead people.
    'min_years_dead' => (int) env('PERSONA_MIN_YEARS_DEAD', 70),

    // Chat model (PERSONA_CHAT_MODEL). Named here, not the AI default: the admin's
    // default model is tuned for editing tools and was unavailable when this shipped.
    'chat_model' => env('PERSONA_CHAT_MODEL') ?: 'anthropic/claude-haiku-4.5',
    // The model that writes a persona once (PERSONA_WRITER_MODEL); null = chat model.
    'writer_model' => env('PERSONA_WRITER_MODEL') ?: null,

    'limits' => [
        // Characters per user message (PERSONA_MAX_MESSAGE_CHARS).
        'message_chars' => (int) env('PERSONA_MAX_MESSAGE_CHARS', 2000),
        // Messages a user may send per UTC day, across all people (PERSONA_DAILY_MESSAGES).
        'daily_messages' => (int) env('PERSONA_DAILY_MESSAGES', 100),
        // Requests per minute per user on the send endpoint.
        'per_minute' => (int) env('PERSONA_PER_MINUTE', 12),
        // Output tokens per reply (PERSONA_MAX_OUTPUT_TOKENS).
        'output_tokens' => (int) env('PERSONA_MAX_OUTPUT_TOKENS', 450),
        // Provider timeout in seconds.
        'timeout' => (int) env('PERSONA_TIMEOUT', 60),
    ],

    'context' => [
        // Recent messages sent verbatim (user + assistant), the rest is summarised.
        'recent_messages' => (int) env('PERSONA_RECENT_MESSAGES', 16),
        // Summarise once this many unsummarised messages sit outside the recent window.
        'summarise_after' => (int) env('PERSONA_SUMMARISE_AFTER', 8),
        // Cap of the running summary, in characters.
        'summary_chars' => 1800,
    ],

    'knowledge' => [
        // Token budget of the surroundings briefing (about 4 characters a token).
        'token_budget' => (int) env('PERSONA_KNOWLEDGE_TOKENS', 2500),
        // Radius around the person's places, in degrees (about 111 km each).
        'radius_degrees' => 3.0,
        // Cache of a briefing, in seconds (the data changes rarely).
        'cache_seconds' => 3600,
    ],

    // Bump to regenerate every stored persona on next use.
    'persona_version' => 1,
];
