import { useOnThisDay } from '@/hooks';
import { ON_THIS_DAY_ROWS, yearAnchor } from '@/lib/discover/pick';
import { useToday } from '@/lib/discover/today';
import { yearReason } from '@/lib/discover/wording';
import { ForYouCard } from './ForYouCard';
import { MeanwhileCard, MeanwhileSkeleton } from './MeanwhileCard';
import { OnThisDayCard } from './OnThisDayCard';
import { QuestCard } from './QuestCard';

/**
 * "Meanwhile" on the browse page takes its year from today's "on this day"
 * rows (the first event shown, else the first row) and says so. While those
 * load it is an outline; with none, there is no year to show.
 */
function MeanwhileToday() {
  const { data, isPending } = useOnThisDay(useToday());
  if (isPending) return <MeanwhileSkeleton variant="page" />;
  const anchor = yearAnchor(data?.items.slice(0, ON_THIS_DAY_ROWS.page) ?? []);
  if (!anchor) return null;
  return <MeanwhileCard variant="page" year={anchor.year} reason={yearReason(anchor)} />;
}

/**
 * "Today in the atlas" on the browse page: on this day, meanwhile in that
 * year and the daily expedition as cards that link into the atlas, with the
 * suggestions under them once this browser has opened something there.
 */
export function DiscoverSection() {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 lg:grid-cols-3">
        <OnThisDayCard variant="page" />
        <MeanwhileToday />
        <QuestCard variant="page" />
      </div>
      <ForYouCard variant="page" />
    </div>
  );
}
