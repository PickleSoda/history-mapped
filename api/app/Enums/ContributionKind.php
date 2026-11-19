<?php

declare(strict_types=1);

namespace App\Enums;

/** What a contribution asks for: a text edit to an existing record, or a new record. */
enum ContributionKind: string
{
    /** A correction to one prose field (the original kind). */
    case Edit = 'edit';

    /** A proposed new entity or relationship, created only when a moderator approves. */
    case Create = 'create';
}
