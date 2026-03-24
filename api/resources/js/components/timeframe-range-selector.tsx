import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

type Props = {
    defaultStartYear: number | null;
    defaultEndYear: number | null;
    onApply: (range: {
        startYear: number | null;
        endYear: number | null;
    }) => void;
};

function formatYearInput(year: number | null): string {
    return year == null ? '' : String(year);
}

function parseYearInput(value: string): number | null {
    const trimmed = value.trim();

    if (!trimmed) {
        return null;
    }

    const parsed = Number(trimmed);

    return Number.isFinite(parsed) ? Math.trunc(parsed) : null;
}

export default function TimeframeRangeSelector({
    defaultStartYear,
    defaultEndYear,
    onApply,
}: Props) {
    const [startInput, setStartInput] = useState(
        formatYearInput(defaultStartYear),
    );
    const [endInput, setEndInput] = useState(formatYearInput(defaultEndYear));

    const parsedStart = useMemo(() => parseYearInput(startInput), [startInput]);
    const parsedEnd = useMemo(() => parseYearInput(endInput), [endInput]);

    const hasInvalidInput =
        (startInput.trim() !== '' && parsedStart == null) ||
        (endInput.trim() !== '' && parsedEnd == null);

    return (
        <div className="border-t px-4 py-3">
            <p className="text-xs font-medium">Map Date Range</p>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
                Enter years (negative for BCE, positive for CE), then apply.
            </p>

            <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <Input
                    value={startInput}
                    onChange={(event) => setStartInput(event.target.value)}
                    placeholder="Start year (e.g. -27)"
                    inputMode="numeric"
                />
                <Input
                    value={endInput}
                    onChange={(event) => setEndInput(event.target.value)}
                    placeholder="End year (e.g. 476)"
                    inputMode="numeric"
                />
            </div>

            <div className="mt-2 flex items-center gap-2">
                <Button
                    type="button"
                    size="sm"
                    onClick={() =>
                        onApply({ startYear: parsedStart, endYear: parsedEnd })
                    }
                    disabled={hasInvalidInput}
                >
                    Apply range
                </Button>
                <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                        setStartInput(formatYearInput(defaultStartYear));
                        setEndInput(formatYearInput(defaultEndYear));
                        onApply({
                            startYear: defaultStartYear,
                            endYear: defaultEndYear,
                        });
                    }}
                >
                    Reset
                </Button>
            </div>
        </div>
    );
}
