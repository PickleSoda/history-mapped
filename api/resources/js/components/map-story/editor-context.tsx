import { createContext, useContext } from 'react';
import type {
    LinkedEntity,
    LngLat,
    StoryDoc,
    StoryVocabulary,
} from '@/lib/map-story-doc';

export type ChronicleEntry = {
    sequence_order: number;
    start_year: number | null;
    text: string | null;
};

export type StoryEditor = {
    doc: StoryDoc;
    /** Change the draft: `fn` edits a copy in place. */
    edit: (fn: (draft: StoryDoc) => void) => void;
    /** Replace the draft (renames that rewrite references). */
    replace: (next: StoryDoc) => void;
    vocab: StoryVocabulary;
    errors: string[];
    warnings: string[];
    /** Q-id → atlas entity, for the link checks. */
    linked: Record<string, LinkedEntity>;
    addLinked: (wikidata: string, entity: LinkedEntity) => void;
    entries: ChronicleEntry[];
    /** The step shown in the preview (and edited in the Steps tab). */
    step: number;
    setStep: (index: number) => void;
    /** Ask the preview for a point or a path; the callback gets it. */
    pick: (
        mode: 'point' | 'path',
        done: (value: LngLat | LngLat[]) => void,
    ) => void;
    /** Ask the preview for its camera. */
    requestCamera: (
        done: (camera: {
            center: LngLat;
            zoom: number;
            bearing: number;
        }) => void,
    ) => void;
};

export const StoryEditorContext = createContext<StoryEditor | null>(null);

export function useStoryEditor(): StoryEditor {
    const value = useContext(StoryEditorContext);

    if (!value) {
        throw new Error('useStoryEditor needs a StoryEditorContext provider');
    }

    return value;
}
