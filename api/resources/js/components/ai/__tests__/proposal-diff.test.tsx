// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import { ProposalDiff } from '@/components/ai/proposal-diff';

afterEach(() => {
    cleanup();
});

describe('ProposalDiff', () => {
    it('renders nothing when the diff is summary-only', () => {
        const { container } = render(
            <ProposalDiff
                tool="create_relationship"
                humanDiff={{ summary: 's' }}
            />,
        );

        expect(container).toBeEmptyDOMElement();
    });

    it('shows a toggle and reveals/hides rows on click', () => {
        render(
            <ProposalDiff
                tool="update_entity_fields"
                humanDiff={{
                    summary: 'Update fields',
                    diff: { founding_year: { from: 1921, to: 1922 } },
                }}
            />,
        );

        // Collapsed by default: values hidden, toggle present.
        const toggle = screen.getByRole('button', { name: /show changes/i });

        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        expect(screen.queryByText(/1922/)).not.toBeInTheDocument();

        // Expand → rows visible.
        fireEvent.click(toggle);
        expect(
            screen.getByRole('button', { name: /hide changes/i }),
        ).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByText(/1921/)).toBeInTheDocument();
        expect(screen.getByText(/1922/)).toBeInTheDocument();

        // Collapse again → rows hidden.
        fireEvent.click(screen.getByRole('button', { name: /hide changes/i }));
        expect(screen.queryByText(/1922/)).not.toBeInTheDocument();
    });
});
