<?php

declare(strict_types=1);

namespace App\Enums;

enum SourceType: string
{
    case VideoTranscript = 'video_transcript';
    case Article = 'article';
    case BookExcerpt = 'book_excerpt';
    case Manual = 'manual';
}
