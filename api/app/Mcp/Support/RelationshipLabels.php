<?php

declare(strict_types=1);

namespace App\Mcp\Support;

/**
 * A relationship type as a verb phrase from one entity's point of view. The
 * enum has no labels, and its values read from the source entity's side
 * ("rules"), so the target's side needs the inverse ("ruled by").
 */
final class RelationshipLabels
{
    /** @var array<string, string> type => phrase read from the target's side */
    private const INVERSE = [
        'rules' => 'ruled by',
        'governed_by' => 'governs',
        'vassal_of' => 'suzerain of',
        'suzerain_of' => 'vassal of',
        'succeeded_by' => 'succeeds',
        'preceded_by' => 'precedes',
        'part_of' => 'contains',
        'contains' => 'part of',
        'capital_of' => 'has capital',
        'split_from' => 'split into',
        'merged_into' => 'absorbed',
        'born_in' => 'birthplace of',
        'died_in' => 'place of death of',
        'resided_in' => 'home of',
        'commanded' => 'commanded by',
        'commanded_by' => 'commander of',
        'founded' => 'founded by',
        'authored' => 'authored by',
        'commissioned' => 'commissioned by',
        'parent_of' => 'child of',
        'child_of' => 'parent of',
        'mentor_of' => 'student of',
        'student_of' => 'mentor of',
        'assassinated_by' => 'assassinated',
        'member_of_dynasty' => 'has member',
        'patron_of' => 'patronised by',
        'participated_in' => 'had participant',
        'fought_at' => 'site of fighting for',
        'defeated_at' => 'site where defeated',
        'victorious_at' => 'site of victory for',
        'stationed_at' => 'garrisoned by',
        'recruited_from' => 'recruited from this',
        'controlled_by' => 'controls',
        'minted_by' => 'minted',
        'adheres_to' => 'followed by',
        'official_religion_of' => 'has official religion',
        'persecuted_by' => 'persecuted',
        'influenced_by' => 'influenced',
        'inspired' => 'inspired by',
        'built_by' => 'built',
        'destroyed_by' => 'destroyed',
        'restored_by' => 'restored',
        'caused' => 'caused by',
        'resulted_from' => 'led to',
        'contributed_to' => 'helped by',
        'enabled' => 'enabled by',
        'prevented' => 'prevented by',
        'weakened' => 'weakened by',
        'strengthened' => 'strengthened by',
        'invented' => 'invented by',
        'adopted' => 'adopted by',
        'replaced_by' => 'replaces',
        'signed_by' => 'signed',
        'violated_by' => 'violated',
        'guaranteed_by' => 'guaranteed',
        'mediated_by' => 'mediated',
        'enforced_by' => 'enforced',
    ];

    /**
     * Symmetric or already direction-neutral types read the same both ways.
     * Anything else without an inverse above falls back to "<type> (reverse)".
     */
    public static function label(string $type, bool $outgoing): string
    {
        $phrase = Text::humanize($type);
        if ($outgoing) {
            return $phrase;
        }

        return self::INVERSE[$type] ?? (self::symmetric($type) ? $phrase : $phrase.' (reverse)');
    }

    private static function symmetric(string $type): bool
    {
        return in_array($type, ['allied_with', 'at_war_with', 'married_to', 'sibling_of', 'trades_with', 'connects'], true);
    }
}
