import { Meter, formatBytes } from "@canonical/maas-react-components";
import { ContextualMenu } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { ComposeFormValues, DiskField } from "../../ComposeForm";

import { COLOURS } from "@/app/base/constants";
import { getSortedPoolsArray } from "@/app/kvm/utils";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod, PodDetails } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";

type RequestMap = Record<string, number>;

type SelectPool = (poolName?: string) => void;

type Props = {
  disk: DiskField;
  hostId: Pod["id"];
  selectPool: SelectPool;
};

const byteDisplay = (bytes: number, roundDown = false): number =>
  formatBytes(
    { value: bytes, unit: "B" },
    {
      convertTo: "GB",
      roundFunc: roundDown ? "floor" : "round",
    }
  ).value;

const generateDropdownContent = (
  pod: PodDetails,
  disk: DiskField,
  requests: RequestMap,
  selectPool: SelectPool
): React.ReactElement => {
  const sortedPools = getSortedPoolsArray(
    pod.resources.storage_pools,
    pod.default_storage_pool
  );
  return (
    <>
      <div className="kvm-pool-select__header p-table__header">
        <div></div>
        <div>Storage</div>
        <div className="u-align--right">Type</div>
        <ul className="p-inline-list u-default-text u-no-margin--bottom">
          <li className="p-inline-list__item">
            <i aria-label="Allocated" className="p-circle--link is-inline"></i>
            Allocated
          </li>
          <li className="p-inline-list__item">
            <i
              aria-label="Requested"
              className="p-circle--positive is-inline"
            ></i>
            Requested
          </li>
          <li className="p-inline-list__item">
            <i aria-label="Free" className="p-circle--link-faded is-inline"></i>
            Free
          </li>
        </ul>
      </div>
      {sortedPools.map(([name, pool]) => {
        const isSelected = name === disk.location;
        const isDefault = "id" in pool && pool.id === pod.default_storage_pool;

        // Convert requests into bytes
        const requested = requests[name]
          ? formatBytes(
              { value: requests[name], unit: "GB" },
              { convertTo: "B" }
            ).value
          : 0;
        const pendingRequest = isSelected
          ? 0
          : formatBytes({ value: disk.size, unit: "GB" }, { convertTo: "B" })
              .value;
        // Free amount is the actual space available in the pool, less any
        // existing storage requests (including the current request).
        const freeBytes =
          pool.total - pool.allocated_tracked - pool.allocated_other;
        const free = formatBytes(
          { value: freeBytes - requested - pendingRequest, unit: "B" },
          {
            convertTo: "B",
            roundFunc: "floor",
          }
        ).value;

        return (
          <button
            className="kvm-pool-select__button p-button--base"
            data-testid={`kvm-pool-select-${name}`}
            disabled={free < 0}
            key={`${disk.id}-${name}`}
            onClick={() => {
              selectPool(name);
            }}
            type="button"
          >
            <div className="kvm-pool-select__row">
              <div>
                {isSelected && (
                  <i aria-label="selected" className="p-icon--tick"></i>
                )}
              </div>
              <div>
                <strong data-testid="pool-name">
                  {isDefault ? `${name} (default)` : name}
                </strong>
                <br />
                <span className="u-text--light">{pool.path}</span>
              </div>
              <div className="u-align--right">
                {pool.backend}
                <br />
                <span data-testid="total">{`${byteDisplay(
                  pool.total
                )}GB`}</span>
              </div>
              <Meter
                className="u-no-margin--bottom"
                data={[
                  {
                    color: COLOURS.LINK,
                    value: pool.allocated_other + pool.allocated_tracked,
                  },
                  {
                    color: COLOURS.POSITIVE,
                    value: requested,
                  },
                  {
                    color: COLOURS.POSITIVE_FADED,
                    value: pendingRequest,
                  },
                  {
                    color: COLOURS.LINK_FADED,
                    value: free >= 0 ? free : 0,
                  },
                ]}
                max={pool.total}
              >
                <Meter.Label>
                  {free >= 0 ? (
                    <ul className="p-inline-list u-no-margin--bottom">
                      <li
                        className="p-inline-list__item"
                        data-testid="allocated"
                      >
                        <i className="p-circle--link is-inline"></i>
                        {`${byteDisplay(
                          pool.allocated_other + pool.allocated_tracked
                        )}GB`}
                      </li>
                      {requested !== 0 && (
                        <li
                          className="p-inline-list__item"
                          data-testid="requested"
                        >
                          <i className="p-circle--positive is-inline"></i>
                          {`${byteDisplay(requested)}GB`}
                        </li>
                      )}
                      <li className="p-inline-list__item" data-testid="free">
                        <i className="p-circle--link-faded is-inline"></i>
                        {`${byteDisplay(free, true)}GB`}
                      </li>
                    </ul>
                  ) : (
                    <div>
                      <i className="p-icon--warning is-inline"></i>
                      Only {byteDisplay(freeBytes, true)} GB available in {name}
                      .
                    </div>
                  )}
                </Meter.Label>
              </Meter>
            </div>
          </button>
        );
      })}
    </>
  );
};

export const PoolSelect = ({
  disk,
  hostId,
  selectPool,
}: Props): React.ReactElement => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  ) as PodDetails;
  const { values } = useFormikContext<ComposeFormValues>();

  const { disks } = values;
  const requests = disks.reduce<RequestMap>((requests, disk) => {
    if (requests[disk.location]) {
      requests[disk.location] += disk.size;
    } else {
      requests[disk.location] = disk.size;
    }
    return requests;
  }, {});

  return (
    <ContextualMenu
      className="kvm-pool-select"
      constrainPanelWidth
      dropdownClassName="kvm-pool-select__dropdown"
      hasToggleIcon
      position="left"
      toggleClassName="kvm-pool-select__toggle"
      toggleLabel={disk.location || "Select pool"}
    >
      {generateDropdownContent(pod, disk, requests, selectPool)}
    </ContextualMenu>
  );
};

export default PoolSelect;
