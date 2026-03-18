<?php

declare(strict_types=1);

namespace App\Enums;

enum VerificationStatus: string
{
    case PipelineDraft = 'pipeline_draft';
    case AutoValidated = 'auto_validated';
    case NeedsReview = 'needs_review';
    case InReview = 'in_review';
    case HumanVerified = 'human_verified';
    case ExpertVerified = 'expert_verified';
    case Flagged = 'flagged';
    case Rejected = 'rejected';
    case Merged = 'merged';
}
