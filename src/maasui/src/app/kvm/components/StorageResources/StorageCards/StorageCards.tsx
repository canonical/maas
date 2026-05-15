import { useCallback, useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import { formatBytes } from "@canonical/maas-react-components";
import { useListener } from "@canonical/react-components/dist/hooks";

import { COLOURS } from "@/app/base/constants";
import StoragePopover from "@/app/kvm/components/StorageColumn/StoragePopover";
import type { KVMStoragePoolResources } from "@/app/kvm/types";
import { calcFreePoolStorage, getSortedPoolsArray } from "@/app/kvm/utils";
import type { Pod } from "@/app/store/pod/types";

type Props = {
  defaultPoolId?: Pod["default_storage_pool"];
  pools: KVMStoragePoolResources;
};
type CardSize = "large" | "medium" | "small";

const MIN_ASPECT_RATIO = 0.65;
const SMALL_CARD_HEIGHT = 50;
export const SMALL_MIN_WIDTH = Math.ceil(SMALL_CARD_HEIGHT * MIN_ASPECT_RATIO);
export const MEDIUM_MIN_WIDTH = SMALL_MIN_WIDTH * 1.5;
export const LARGE_MIN_WIDTH = SMALL_MIN_WIDTH * 3;

export const updateCardSize = (
  width: number,
  numCards: number,
  setCardSize: Dispatch<SetStateAction<CardSize>>
): void => {
  if (width >= numCards * LARGE_MIN_WIDTH) {
    setCardSize("large");
  } else if (width * 2 >= numCards * MEDIUM_MIN_WIDTH) {
    setCardSize("medium");
  } else {
    setCardSize("small");
  }
};

const StorageCards = ({
  defaultPoolId,
  pools,
}: Props): React.ReactElement | null => {
  const [cardSize, setCardSize] = useState<CardSize>("small");
  const el = useRef<HTMLDivElement>(null);
  const sortedPools = getSortedPoolsArray(pools, defaultPoolId);
  const onResize = useCallback(() => {
    if (el?.current?.offsetWidth) {
      updateCardSize(el?.current?.offsetWidth, sortedPools.length, setCardSize);
    }
  }, [sortedPools.length]);
  useEffect(onResize, [onResize]);
  useListener(window, onResize, "resize", true);

  return (
    <div
      aria-label="storage cards"
      className={`storage-cards storage-cards--${cardSize}`}
      ref={el}
    >
      {sortedPools.map(([name, pool]) => {
        const allocatedWidth = (pool.allocated_tracked / pool.total) * 100;
        const otherWidth =
          allocatedWidth + (pool.allocated_other / pool.total) * 100;
        const total = formatBytes({ value: pool.total, unit: "B" });
        const allocated = formatBytes(
          { value: pool.allocated_tracked + pool.allocated_other, unit: "B" },
          { convertTo: total.unit }
        );
        const free = formatBytes(
          { value: calcFreePoolStorage(pool), unit: "B" },
          {
            convertTo: total.unit,
          }
        );

        return (
          <StoragePopover
            defaultPoolId={defaultPoolId}
            key={`storage-popover-${name}`}
            pools={{ [name]: pool } as KVMStoragePoolResources}
          >
            <div className="storage-card-container">
              <div className="storage-card">
                <div className="storage-card__text-container">
                  {cardSize === "large" ? (
                    <>
                      <div className="u-truncate">{name}</div>
                      <div className="p-text--x-small-capitalised u-text--muted u-no-margin--bottom">
                        Free
                      </div>
                      <div className="u-align--right u-sv1">
                        {free.value}
                        {free.unit}
                      </div>
                      <hr />
                      <div className="p-text--x-small-capitalised u-text--muted u-no-margin--bottom">
                        Allocated
                      </div>
                      <div className="u-align--right">
                        {allocated.value}
                        {allocated.unit}
                      </div>
                    </>
                  ) : (
                    <div className="storage-card__small-text u-align--right u-nudge-right--x-small u-truncate">
                      {name}
                    </div>
                  )}
                </div>
                <div
                  className="storage-card__meter"
                  data-testid="storage-card-meter"
                  style={{
                    backgroundImage: `linear-gradient(
                      to right,
                      ${COLOURS.LINK} 0,
                      ${COLOURS.LINK} ${allocatedWidth}%,
                      ${COLOURS.POSITIVE} ${allocatedWidth}%,
                      ${COLOURS.POSITIVE} ${otherWidth}%,
                      ${COLOURS.LINK_FADED} ${otherWidth}%,
                      ${COLOURS.LINK_FADED} 100%
                    )`,
                  }}
                ></div>
              </div>
            </div>
          </StoragePopover>
        );
      })}
    </div>
  );
};

export default StorageCards;
