<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests\Concerns;

/**
 * Lets a FormRequest accept `?key=a,b,c` (or `key[]=a`) and validate it as an array.
 */
trait ParsesCsvParams
{
    /**
     * @param  list<string>  $keys
     */
    protected function explodeCsv(array $keys): void
    {
        $merge = [];
        foreach ($keys as $key) {
            $value = $this->query($key);
            if (is_string($value)) {
                $merge[$key] = array_values(array_filter(array_map('trim', explode(',', $value)), fn (string $v): bool => $v !== ''));
            }
        }
        $this->merge($merge);
    }
}
