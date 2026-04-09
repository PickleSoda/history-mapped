// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import type { EntityFormOptions } from '@/types';
import EntityForm, { defaultFormData } from '../entity-form';

const options: EntityFormOptions = {
    types: [{ value: 'city', label: 'City', group: 'PLACE' }],
    groups: [{ value: 'PLACE', label: 'PLACE' }],
    statuses: [{ value: 'pipeline_draft', label: 'Pipeline Draft' }],
    confidences: [{ value: 'high', label: 'High' }],
    dateMethods: [{ value: 'human_assigned', label: 'Human Assigned' }],
    durationTypes: [{ value: 'period', label: 'Period' }],
    locationMethods: [{ value: 'human_assigned', label: 'Human Assigned' }],
    iconClasses: [{ value: 'map_pin', label: 'Map Pin' }],
};

describe('EntityForm hierarchy controls', () => {
    it('renders parent and successor fields and updates values', () => {
        const onChange = vi.fn();

        render(
            <EntityForm
                data={defaultFormData()}
                errors={{}}
                processing={false}
                options={options}
                onChange={onChange}
                onSubmit={(e) => e.preventDefault()}
            />,
        );

        const parentInput = screen.getByLabelText(/Parent Entity ID/i);
        const successorInput = screen.getByLabelText(/Successor Entity ID/i);

        fireEvent.change(parentInput, {
            target: { value: '11111111-1111-1111-1111-111111111111' },
        });
        fireEvent.change(successorInput, {
            target: { value: '22222222-2222-2222-2222-222222222222' },
        });

        expect(onChange).toHaveBeenCalledWith(
            'parent_entity_id',
            '11111111-1111-1111-1111-111111111111',
        );
        expect(onChange).toHaveBeenCalledWith(
            'successor_entity_id',
            '22222222-2222-2222-2222-222222222222',
        );
    });
});
