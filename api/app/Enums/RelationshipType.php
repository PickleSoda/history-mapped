<?php

declare(strict_types=1);

namespace App\Enums;

enum RelationshipType: string
{
    // Political
    case Rules = 'rules';
    case GovernedBy = 'governed_by';
    case VassalOf = 'vassal_of';
    case SuzerainOf = 'suzerain_of';
    case AlliedWith = 'allied_with';
    case AtWarWith = 'at_war_with';
    case SucceededBy = 'succeeded_by';
    case PrecededBy = 'preceded_by';
    case PartOf = 'part_of';
    case Contains = 'contains';
    case CapitalOf = 'capital_of';
    case SplitFrom = 'split_from';
    case MergedInto = 'merged_into';

    // Person
    case BornIn = 'born_in';
    case DiedIn = 'died_in';
    case ResidedIn = 'resided_in';
    case Commanded = 'commanded';
    case Founded = 'founded';
    case Authored = 'authored';
    case Commissioned = 'commissioned';
    case MarriedTo = 'married_to';
    case ParentOf = 'parent_of';
    case ChildOf = 'child_of';
    case SiblingOf = 'sibling_of';
    case MentorOf = 'mentor_of';
    case StudentOf = 'student_of';
    case AssassinatedBy = 'assassinated_by';
    case MemberOfDynasty = 'member_of_dynasty';
    case PatronOf = 'patron_of';

    // Military
    case ParticipatedIn = 'participated_in';
    case FoughtAt = 'fought_at';
    case DefeatedAt = 'defeated_at';
    case VictoriousAt = 'victorious_at';
    case StationedAt = 'stationed_at';
    case RecruitedFrom = 'recruited_from';
    case CommandedBy = 'commanded_by';

    // Economic
    case TradesWith = 'trades_with';
    case Connects = 'connects';
    case Produces = 'produces';
    case Extracts = 'extracts';
    case Supplies = 'supplies';
    case ControlledBy = 'controlled_by';
    case PassesThrough = 'passes_through';
    case MintedBy = 'minted_by';
    case UsedCurrency = 'used_currency';

    // Religious/Cultural
    case AdheresTo = 'adheres_to';
    case OfficialReligionOf = 'official_religion_of';
    case PersecutedBy = 'persecuted_by';
    case InfluencedBy = 'influenced_by';
    case Inspired = 'inspired';
    case SchismFrom = 'schism_from';
    case TranslatedInto = 'translated_into';
    case LocatedAt = 'located_at';
    case BuiltBy = 'built_by';
    case DestroyedBy = 'destroyed_by';
    case RestoredBy = 'restored_by';

    // Causal
    case Caused = 'caused';
    case ResultedFrom = 'resulted_from';
    case ContributedTo = 'contributed_to';
    case Enabled = 'enabled';
    case Prevented = 'prevented';
    case Weakened = 'weakened';
    case Strengthened = 'strengthened';

    // Knowledge
    case Invented = 'invented';
    case Adopted = 'adopted';
    case TaughtAt = 'taught_at';
    case SpreadTo = 'spread_to';
    case RequiredBy = 'required_by';
    case ReplacedBy = 'replaced_by';

    // Diplomatic
    case SignedBy = 'signed_by';
    case ViolatedBy = 'violated_by';
    case GuaranteedBy = 'guaranteed_by';
    case MediatedBy = 'mediated_by';
    case EnforcedBy = 'enforced_by';
}
