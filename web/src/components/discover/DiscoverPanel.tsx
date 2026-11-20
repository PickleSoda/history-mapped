import { useEffect, useState } from 'react';
import { useTimeState } from '@/hooks';
import { instantYear } from '@/lib/format';
import { ForYouCard } from './ForYouCard';
import { MeanwhileCard } from './MeanwhileCard';
import { OnThisDayCard } from './OnThisDayCard';
import { QuestCard } from './QuestCard';

/** How long the timeline has to rest before "Meanwhile" asks about its year. */
const YEAR_SETTLE_MS = 400;

/** `value`, once it has stopped changing for `ms`. */
function useSettled<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

/**
 * The Today tab of the atlas sidebar and sheet: the daily expedition, what
 * happened on this day, what was going on across the world in the timeline's
 * year, and suggestions from what this browser opened lately.
 *
 * "Meanwhile" follows the timeline, but only once it rests: playing or
 * stepping through the years would otherwise ask about every one of them.
 */
export function DiscoverPanel() {
  const { time } = useTimeState();
  const year = useSettled(instantYear(time), YEAR_SETTLE_MS);
  return (
    <div className="space-y-3 p-3">
      <QuestCard variant="panel" />
      <OnThisDayCard variant="panel" />
      <MeanwhileCard variant="panel" year={year} />
      <ForYouCard variant="panel" />
    </div>
  );
}
