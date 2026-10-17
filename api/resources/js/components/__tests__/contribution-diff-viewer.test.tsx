// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import {
    ContributionDiffViewer,
    diffSides,
    diffStats,
} from '@/components/contribution-diff-viewer';
import type { Diff } from '@/types';

afterEach(() => {
    cleanup();
});

// "Rome was founded in 753 BC." → "Rome was traditionally founded in 753 BCE."
const DIFF: Diff = [
    ['=', 'Rome was '],
    ['+', 'traditionally '],
    ['=', 'founded in 753 '],
    ['-', 'BC'],
    ['+', 'BCE'],
    ['=', '.'],
];

describe('diff helpers', () => {
    it('rebuilds the base and proposed texts', () => {
        expect(diffSides(DIFF)).toEqual({
            base: 'Rome was founded in 753 BC.',
            proposed: 'Rome was traditionally founded in 753 BCE.',
        });
    });

    it('counts changed words only', () => {
        expect(diffStats(DIFF)).toEqual({ added: 2, removed: 1 });
        expect(
            diffStats([
                ['+', ' , '],
                ['-', '\n'],
            ]),
        ).toEqual({
            added: 0,
            removed: 0,
        });
    });
});

describe('ContributionDiffViewer', () => {
    it('renders inline removals and additions with screen-reader labels', () => {
        const { container } = render(<ContributionDiffViewer diff={DIFF} />);

        const removed = container.querySelectorAll('del');
        const added = container.querySelectorAll('ins');
        expect([...removed].map((n) => n.textContent)).toEqual([
            '[removed: BC]',
        ]);
        expect([...added].map((n) => n.textContent)).toEqual([
            '[added: traditionally ]',
            '[added: BCE]',
        ]);
        expect(screen.getByText('+2')).toBeInTheDocument();
        expect(screen.getByText('−1')).toBeInTheDocument();
    });

    it('switches to side by side, keeping each side to its own ops', () => {
        render(
            <ContributionDiffViewer
                diff={DIFF}
                baseLabel="Current text"
                proposedLabel="Proposed text"
            />,
        );

        fireEvent.click(screen.getByRole('radio', { name: /side by side/i }));

        const base = screen.getByRole('region', { name: 'Current text' });
        const proposed = screen.getByRole('region', { name: 'Proposed text' });
        expect(base.querySelector('ins')).toBeNull();
        expect(base.querySelector('del')).toHaveTextContent('BC');
        expect(proposed.querySelector('del')).toBeNull();
        expect(proposed.querySelectorAll('ins')).toHaveLength(2);
    });

    it('marks whitespace-only changes so they stay visible', () => {
        const { container } = render(
            <ContributionDiffViewer
                diff={[
                    ['=', 'one'],
                    ['+', '\n'],
                    ['=', 'two'],
                ]}
            />,
        );

        expect(container.querySelector('ins')).toHaveTextContent('↵');
    });

    it('shows an empty base as a placeholder for a suggestion on a missing field', () => {
        render(
            <ContributionDiffViewer
                diff={[['+', 'A brand new summary.']]}
                baseLabel="Submitted against"
                proposedLabel="Proposed text"
            />,
        );

        expect(
            screen.getByRole('region', { name: /changes from/i }),
        ).toHaveTextContent('[added: A brand new summary.]');

        fireEvent.click(screen.getByRole('radio', { name: /side by side/i }));

        expect(
            screen.getByRole('region', { name: 'Submitted against' }),
        ).toHaveTextContent('(empty)');
        expect(
            screen.getByRole('region', { name: 'Proposed text' }),
        ).toHaveTextContent('A brand new summary.');
    });

    it('says when there is nothing to show', () => {
        render(<ContributionDiffViewer diff={[['=', 'same']]} />);

        expect(screen.getByText('No changes.')).toBeInTheDocument();
    });
});
