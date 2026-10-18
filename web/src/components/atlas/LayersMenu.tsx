import { Menu } from '@base-ui/react/menu';
import { Check, Layers } from 'lucide-react';
import { MENU_ITEM, POPUP } from '@/components/account/styles';
import { useBasemap } from '@/hooks';
import { BASEMAPS } from '@/lib/map-config';
import { cn } from '@/lib/utils';
import type { BasemapId } from '@/types/atlas';

/** Basemap choices in menu order. */
export const BASEMAP_IDS = Object.keys(BASEMAPS) as BasemapId[];

/** Top-bar Layers control: pick the OpenHistoricalMap basemap style. */
export function LayersMenu() {
  const { basemap, setBasemap } = useBasemap();

  return (
    <Menu.Root>
      <Menu.Trigger
        aria-label="Layers"
        className="grid size-9 place-items-center rounded-lg text-muted-foreground outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring data-[popup-open]:bg-muted data-[popup-open]:text-foreground"
      >
        <Layers size={16} />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner sideOffset={8} align="end" className="z-50">
          <Menu.Popup className={cn(POPUP, 'w-60')}>
            <Menu.Group>
              <Menu.GroupLabel className="px-2 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Basemap
              </Menu.GroupLabel>
              <Menu.RadioGroup
                value={basemap}
                onValueChange={(value: BasemapId) => void setBasemap(value)}
              >
                {BASEMAP_IDS.map((id) => (
                  <Menu.RadioItem
                    key={id}
                    value={id}
                    closeOnClick
                    className={cn(MENU_ITEM, 'items-start')}
                  >
                    <span className="grid size-4 flex-none place-items-center pt-0.5">
                      <Menu.RadioItemIndicator>
                        <Check size={14} />
                      </Menu.RadioItemIndicator>
                    </span>
                    <span className="min-w-0">
                      <span className="block">{BASEMAPS[id].label}</span>
                      <span className="block text-[11px] text-muted-foreground">
                        {BASEMAPS[id].hint}
                      </span>
                    </span>
                  </Menu.RadioItem>
                ))}
              </Menu.RadioGroup>
            </Menu.Group>
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}
