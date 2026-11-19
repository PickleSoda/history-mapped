<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

/**
 * Base for /mcp/contribute tests. Passport needs an RSA key pair to build its
 * resource server; tests generate a throwaway one in memory and hand it over
 * through the same PASSPORT_*_KEY config the app uses, so no key files exist
 * or are needed.
 */
abstract class ContributeTestCase extends McpTestCase
{
    /** @var array{private: string, public: string}|null */
    private static ?array $keys = null;

    protected function setUp(): void
    {
        parent::setUp();

        self::$keys ??= (function (): array {
            $key = openssl_pkey_new(['private_key_bits' => 2048, 'private_key_type' => OPENSSL_KEYTYPE_RSA]);
            openssl_pkey_export($key, $private);

            return ['private' => $private, 'public' => openssl_pkey_get_details($key)['key']];
        })();

        config([
            'passport.private_key' => self::$keys['private'],
            'passport.public_key' => self::$keys['public'],
        ]);
    }
}
