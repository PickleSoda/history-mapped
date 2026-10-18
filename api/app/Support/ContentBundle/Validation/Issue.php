<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

/**
 * One validation finding, rendered as `file:line: field: message`. `id` is the bundle line's record id
 * when known; the validator uses it to downgrade errors on lines that are unchanged since export.
 */
final readonly class Issue
{
    public const ERROR = 'error';

    public const WARNING = 'warning';

    public const PACKAGE = 'package';

    public const STRUCTURE = 'structure';

    public const RECORDS = 'records';

    public const REFERENCES = 'references';

    public function __construct(
        public string $severity,
        public string $layer,
        public ?string $file,
        public ?int $line,
        public ?string $field,
        public string $message,
        public ?string $id = null,
        public bool $unchanged = false,
    ) {}

    public static function error(string $layer, string $message, ?string $file = null, ?int $line = null, ?string $field = null, ?string $id = null): self
    {
        return new self(self::ERROR, $layer, $file, $line, $field, $message, $id);
    }

    public static function warning(string $layer, string $message, ?string $file = null, ?int $line = null, ?string $field = null, ?string $id = null): self
    {
        return new self(self::WARNING, $layer, $file, $line, $field, $message, $id);
    }

    public function isError(): bool
    {
        return $this->severity === self::ERROR;
    }

    public function asWarning(string $suffix): self
    {
        return new self(self::WARNING, $this->layer, $this->file, $this->line, $this->field, $this->message.$suffix, $this->id, true);
    }

    /** @return array{severity: string, layer: string, file: ?string, line: ?int, field: ?string, message: string, id: ?string, unchanged: bool} */
    public function toArray(): array
    {
        return [
            'severity' => $this->severity,
            'layer' => $this->layer,
            'file' => $this->file,
            'line' => $this->line,
            'field' => $this->field,
            'message' => $this->message,
            'id' => $this->id,
            'unchanged' => $this->unchanged,
        ];
    }

    public function __toString(): string
    {
        $where = ($this->file ?? '').($this->line !== null ? ':'.$this->line : '');

        return implode(': ', array_filter([$where, $this->field, $this->message], fn (?string $p) => $p !== null && $p !== ''));
    }
}
