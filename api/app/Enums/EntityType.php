<?php

declare(strict_types=1);

namespace App\Enums;

enum EntityType: string
{
    // POLITY
    case PoliticalEntity = 'political_entity';
    case Dynasty = 'dynasty';
    case Person = 'person';
    case MilitaryUnit = 'military_unit';
    case DiplomaticRelationship = 'diplomatic_relationship';
    case SocialClass = 'social_class';

    // PLACE
    case City = 'city';
    case InfrastructureMonument = 'infrastructure_monument';
    case ExtractionInfra = 'extraction_infra';
    case EducationalInstitution = 'educational_institution';

    // EVENT
    case EventWar = 'event_war';
    case EventBattle = 'event_battle';
    case EventTreaty = 'event_treaty';
    case EventRebellion = 'event_rebellion';
    case EventNaturalDisaster = 'event_natural_disaster';
    case EventTechAdoption = 'event_tech_adoption';
    case EventLegalReform = 'event_legal_reform';
    case Migration = 'migration';
    case EpidemicDisease = 'epidemic_disease';

    // ECONOMY
    case TradeRoute = 'trade_route';
    case NaturalResource = 'natural_resource';
    case CurrencyMonetarySystem = 'currency_monetary_system';

    // CULTURE
    case CulturalWork = 'cultural_work';
    case IntellectualMovement = 'intellectual_movement';
    case ArchaeologicalCulture = 'archaeological_culture';
    case Language = 'language';
    case ReligiousText = 'religious_text';
    case LegalCode = 'legal_code';
    case ReligiousMovement = 'religious_movement';
    case Technology = 'technology';

    public function group(): EntityGroup
    {
        return match ($this) {
            self::PoliticalEntity,
            self::Dynasty,
            self::Person,
            self::MilitaryUnit,
            self::DiplomaticRelationship,
            self::SocialClass => EntityGroup::Polity,

            self::City,
            self::InfrastructureMonument,
            self::ExtractionInfra,
            self::EducationalInstitution => EntityGroup::Place,

            self::EventWar,
            self::EventBattle,
            self::EventTreaty,
            self::EventRebellion,
            self::EventNaturalDisaster,
            self::EventTechAdoption,
            self::EventLegalReform,
            self::Migration,
            self::EpidemicDisease => EntityGroup::Event,

            self::TradeRoute,
            self::NaturalResource,
            self::CurrencyMonetarySystem => EntityGroup::Economy,

            self::CulturalWork,
            self::IntellectualMovement,
            self::ArchaeologicalCulture,
            self::Language,
            self::ReligiousText,
            self::LegalCode,
            self::ReligiousMovement,
            self::Technology => EntityGroup::Culture,
        };
    }
}
