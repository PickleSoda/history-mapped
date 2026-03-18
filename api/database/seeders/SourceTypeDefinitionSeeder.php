<?php

declare(strict_types=1);

namespace Database\Seeders;

use Database\Seeders\Traits\PgArrayLiteral;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

class SourceTypeDefinitionSeeder extends Seeder
{
    use PgArrayLiteral;

    public function run(): void
    {
        $table = 'ref_source_type_definitions';

        DB::table($table)->truncate();

        $definitions = $this->buildDefinitions();

        foreach ($definitions as $definition) {
            DB::table($table)->insert($definition);
        }
    }

    /**
     * @return array<int, array<string, mixed>>
     */
    private function buildDefinitions(): array
    {
        return [
            // ── reliability_tier definitions ─────────────────────
            [
                'definition_id' => 1,
                'enum_name' => 'reliability_tier',
                'enum_value' => 'authoritative',
                'description' => 'Primary sources written during the events, peer-reviewed archaeological reports, inscriptions, coins.',
                'examples' => $this->textArray([
                    'Res Gestae Divi Augusti',
                    'Cuneiform tablets',
                    'Excavation reports from accredited institutions',
                ]),
                'default_confidence' => 'high',
                'requires_corroboration' => false,
                'weight_in_scoring' => 1.5,
                'reviewer_notes' => 'Highest trust tier. Still verify provenance and translation accuracy. Forgeries exist even at this level.',
            ],
            [
                'definition_id' => 2,
                'enum_name' => 'reliability_tier',
                'enum_value' => 'scholarly',
                'description' => 'Academic secondary sources from university presses, peer-reviewed journals.',
                'examples' => $this->textArray([
                    'Journal of Roman Studies articles',
                    'Cambridge Ancient History volumes',
                    'Academic monographs from university presses',
                ]),
                'default_confidence' => 'high',
                'requires_corroboration' => false,
                'weight_in_scoring' => 1.3,
                'reviewer_notes' => 'Check publication date — older scholarship may be superseded by recent discoveries. Prefer post-2000 sources where available.',
            ],
            [
                'definition_id' => 3,
                'enum_name' => 'reliability_tier',
                'enum_value' => 'reference',
                'description' => 'Curated reference databases and well-maintained encyclopedias.',
                'examples' => $this->textArray([
                    'Pleiades',
                    'Wikidata',
                    'Encyclopaedia Britannica',
                    'Princeton Encyclopedia of Classical Sites',
                ]),
                'default_confidence' => 'medium',
                'requires_corroboration' => false,
                'weight_in_scoring' => 1.0,
                'reviewer_notes' => 'Generally reliable for factual data but may simplify scholarly debates. Cross-check coordinates against primary gazetteers.',
            ],
            [
                'definition_id' => 4,
                'enum_name' => 'reliability_tier',
                'enum_value' => 'user_contributed',
                'description' => 'Community-edited sources, blogs, non-peer-reviewed publications.',
                'examples' => $this->textArray([
                    'Wikipedia',
                    'History blogs',
                    'Student papers',
                    'Forum posts',
                ]),
                'default_confidence' => 'low',
                'requires_corroboration' => true,
                'weight_in_scoring' => 0.5,
                'reviewer_notes' => 'Useful for discovery and initial data collection but must be corroborated by higher-tier sources before entity resolution.',
            ],

            // ── document_type definitions ────────────────────────
            [
                'definition_id' => 5,
                'enum_name' => 'document_type',
                'enum_value' => 'academic_paper',
                'description' => 'Peer-reviewed journal article or conference paper.',
                'examples' => $this->textArray([
                    'Journal of Roman Studies (JRS)',
                    'American Journal of Archaeology (AJA)',
                    'Past & Present',
                ]),
                'default_confidence' => null,
                'requires_corroboration' => false,
                'weight_in_scoring' => 1.0,
                'reviewer_notes' => 'Check publication date — older scholarship may be superseded. Look for retraction notices or subsequent corrigenda.',
            ],
            [
                'definition_id' => 6,
                'enum_name' => 'document_type',
                'enum_value' => 'encyclopedia',
                'description' => 'Entry in a reference encyclopedia.',
                'examples' => $this->textArray([
                    'Oxford Classical Dictionary',
                    'Encyclopaedia of Islam (EI2)',
                    'Brill\'s New Pauly',
                ]),
                'default_confidence' => null,
                'requires_corroboration' => false,
                'weight_in_scoring' => 1.0,
                'reviewer_notes' => 'Generally reliable but may be outdated. Check edition date. Prefer most recent edition available.',
            ],
            [
                'definition_id' => 7,
                'enum_name' => 'document_type',
                'enum_value' => 'primary_source',
                'description' => 'Historical document from the period described.',
                'examples' => $this->textArray([
                    'Herodotus, Histories',
                    'Thucydides, History of the Peloponnesian War',
                    'Chinese dynastic histories (Shiji, Hanshu)',
                ]),
                'default_confidence' => null,
                'requires_corroboration' => false,
                'weight_in_scoring' => 1.0,
                'reviewer_notes' => 'Consider author bias, contemporaneity, and genre conventions. Ancient authors often had political agendas. Numbers are frequently exaggerated.',
            ],
            [
                'definition_id' => 8,
                'enum_name' => 'document_type',
                'enum_value' => 'database_export',
                'description' => 'Structured data from a curated scholarly database.',
                'examples' => $this->textArray([
                    'Pleiades JSON export',
                    'DARE database export',
                    'Pelagios linked data',
                ]),
                'default_confidence' => null,
                'requires_corroboration' => false,
                'weight_in_scoring' => 1.0,
                'reviewer_notes' => 'High reliability for coordinates and identifiers. May lack narrative context. Check data freshness and known errata.',
            ],
            [
                'definition_id' => 9,
                'enum_name' => 'document_type',
                'enum_value' => 'web_article',
                'description' => 'Online article from a non-academic source.',
                'examples' => $this->textArray([
                    'Wikipedia',
                    'Livius.org',
                    'World History Encyclopedia',
                ]),
                'default_confidence' => null,
                'requires_corroboration' => true,
                'weight_in_scoring' => 1.0,
                'reviewer_notes' => 'Cross-reference against scholarly sources. Useful for discovery but needs verification before entity data is finalized.',
            ],
        ];
    }
}
