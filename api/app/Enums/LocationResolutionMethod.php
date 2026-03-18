<?php

declare(strict_types=1);

namespace App\Enums;

enum LocationResolutionMethod: string
{
    case OhmNominatim = 'ohm_nominatim';
    case Wikidata = 'wikidata';
    case Geonames = 'geonames';
    case Pleiades = 'pleiades';
    case LlmDisambiguation = 'llm_disambiguation';
    case HumanAssigned = 'human_assigned';
    case SourceDatabase = 'source_database';
}
