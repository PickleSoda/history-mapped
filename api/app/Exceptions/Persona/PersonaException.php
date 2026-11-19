<?php

declare(strict_types=1);

namespace App\Exceptions\Persona;

use Illuminate\Http\JsonResponse;
use RuntimeException;

/**
 * A refusal the chat API explains to the user. `$errorCode` is a stable
 * machine code (the SPA switches on it); the message is shown as is and stays
 * out of character, since it comes from the app, not from the person.
 */
class PersonaException extends RuntimeException
{
    /** @param  array<string, mixed>  $extra */
    public function __construct(
        string $message,
        public readonly string $errorCode,
        public readonly int $status,
        public readonly array $extra = [],
    ) {
        parent::__construct($message);
    }

    public static function notTalkable(): self
    {
        return new self('This person cannot be talked to. Only people who died long ago can.', 'not_talkable', 422);
    }

    public static function dailyLimit(int $limit): self
    {
        return new self(
            "You have reached today's limit of {$limit} messages. It resets at midnight UTC.",
            'daily_limit',
            429,
            ['limit' => $limit],
        );
    }

    public static function busy(): self
    {
        return new self('A reply is already being written. Wait for it, then send your next message.', 'busy', 409);
    }

    public static function providerFailed(): self
    {
        return new self('The reply could not be written just now. Your message was not sent; please try again.', 'provider_failed', 502);
    }

    public function render(): JsonResponse
    {
        return response()->json(['message' => $this->getMessage(), 'code' => $this->errorCode] + $this->extra, $this->status);
    }
}
