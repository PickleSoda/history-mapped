<?php

declare(strict_types=1);

namespace App\Enums;

enum DateResolutionMethod: string
{
    case NlpDirect = 'nlp_direct';
    case NlpApproximate = 'nlp_approximate';
    case LlmReignResolution = 'llm_reign_resolution';
    case EraTableLookup = 'era_table_lookup';
    case LlmContextualInference = 'llm_contextual_inference';
    case HumanAssigned = 'human_assigned';
    case SourceDatabase = 'source_database';
}
