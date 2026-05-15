import type { ReactNode } from "react";
import { Fragment } from "react";

import { Meter, formatBytes } from "@canonical/maas-react-components";

import Popover from "@/app/base/components/Popover";
import { COLOURS } from "@/app/base/constants";
import type { KVMStoragePoolResources } from "@/app/kvm/types";
import { getSortedPoolsArray } from "@/app/kvm/utils";
import type { Pod } from "@/app/store/pod/types";

type Props = {
  children: ReactNode;
  defaultPoolId?: Pod["default_storage_pool"];
  pools: KVMStoragePoolResources;
};

const StoragePopover = ({
  children,
  defaultPoolId,
  pools,
}: Props): React.ReactElement => {
  const sortedPools = getSortedPoolsArray(pools, defaultPoolId);
  const showOthers = sortedPools.some(([, pool]) => pool.allocated_other !== 0);
  return (
    <Popover
      className="storage-popover"
      content={
        <>
          <div className="storage-popover__header p-table__header">
            <div>Storage</div>
            <div className="u-align--right">Type</div>
            <ul className="p-inline-list u-default-text u-no-margin--bottom">
              <li className="p-inline-list__item">
                <i className="p-circle--link is-inline"></i>
                Allocated
              </li>
              {showOthers && (
                <li className="p-inline-list__item" data-testid="others-key">
                  <i className="p-circle--positive is-inline"></i>
                  Others
                </li>
              )}
              <li className="p-inline-list__item">
                <i className="p-circle--link-faded is-inline"></i>
                Free
              </li>
            </ul>
          </div>
          {sortedPools.map(([name, pool]) => {
            const isDefault = "id" in pool && pool.id === defaultPoolId;
            const freeBytes =
              pool.total - pool.allocated_tracked - pool.allocated_other;
            const total = formatBytes({ value: pool.total, unit: "B" });
            const allocated = formatBytes({
              value: pool.allocated_tracked,
              unit: "B",
            });
            const free = formatBytes({ value: freeBytes, unit: "B" });
            const other = formatBytes({
              value: pool.allocated_other,
              unit: "B",
            });

            return (
              <Fragment key={`storage-pool-${name}`}>
                <div className="storage-popover__row">
                  <div>
                    <div className="u-truncate" data-testid="pool-name">
                      <strong>{isDefault ? `${name} (default)` : name}</strong>
                    </div>
                    <div
                      className="u-text--light u-truncate"
                      data-testid="pool-path"
                    >
                      {pool.path}
                    </div>
                  </div>
                  <div className="u-align--right">
                    <div data-testid="pool-backend">{pool.backend}</div>
                    <div>{`${total.value}${total.unit}`}</div>
                  </div>
                  <Meter
                    className="u-no-margin--bottom"
                    data={[
                      {
                        color: COLOURS.LINK,
                        value: pool.allocated_tracked,
                      },
                      {
                        color: COLOURS.POSITIVE,
                        value: pool.allocated_other,
                      },
                      {
                        color: COLOURS.LINK_FADED,
                        value: freeBytes > 0 ? freeBytes : 0,
                      },
                    ]}
                    max={pool.total}
                  >
                    <Meter.Label>
                      {
                        <ul className="p-inline-list u-no-margin--bottom">
                          <li
                            className="p-inline-list__item"
                            data-testid="pool-allocated"
                          >
                            <i className="p-circle--link is-inline"></i>
                            {`${allocated.value}${allocated.unit}`}
                          </li>
                          {showOthers && (
                            <li
                              className="p-inline-list__item"
                              data-testid="pool-others"
                            >
                              <i className="p-circle--positive is-inline"></i>
                              {`${other.value}${other.unit}`}
                            </li>
                          )}
                          <li
                            className="p-inline-list__item"
                            data-testid="pool-free"
                          >
                            <i className="p-circle--link-faded is-inline"></i>
                            {`${free.value}${free.unit}`}
                          </li>
                        </ul>
                      }
                    </Meter.Label>
                  </Meter>
                </div>
              </Fragment>
            );
          })}
        </>
      }
    >
      {children}
    </Popover>
  );
};

export default StoragePopover;
