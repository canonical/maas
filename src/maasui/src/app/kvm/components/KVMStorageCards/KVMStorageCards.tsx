import { useState } from "react";

import { Button, Card, Icon } from "@canonical/react-components";
import pluralize from "pluralize";

import { useSendAnalytics } from "@/app/base/hooks";
import KVMResourceMeter from "@/app/kvm/components/KVMResourceMeter";
import type { KVMStoragePoolResources } from "@/app/kvm/types";
import { calcFreePoolStorage, getSortedPoolsArray } from "@/app/kvm/utils";
import type { Pod } from "@/app/store/pod/types";

export const TRUNCATION_POINT = 3;

type Props = {
  defaultPoolId?: Pod["default_storage_pool"];
  pools: KVMStoragePoolResources;
};

const KVMStorageCards = ({
  defaultPoolId,
  pools,
}: Props): React.ReactElement | null => {
  const [expanded, setExpanded] = useState(false);
  const sendAnalytics = useSendAnalytics();

  const sortedPools = getSortedPoolsArray(pools, defaultPoolId);
  const canBeTruncated = sortedPools.length > TRUNCATION_POINT;
  const shownPools =
    canBeTruncated && !expanded
      ? sortedPools.slice(0, TRUNCATION_POINT)
      : sortedPools;

  return (
    <>
      <h4 className="u-sv1">
        Storage&nbsp;
        <span
          className="p-text--paragraph u-text--light"
          data-testid="sort-label"
        >
          {defaultPoolId ? "(Sorted by id, default first)" : "(Sorted by name)"}
        </span>
      </h4>
      <div className="kvm-storage-cards">
        {shownPools.map(([name, pool]) => {
          return (
            <Card key={`storage-card-${name}`}>
              <h5>
                <span data-testid="pool-name">{name}</span>
                <br />
                <span
                  className="p-text--paragraph u-text--light"
                  title={pool.path}
                >
                  {pool.path}
                </span>
              </h5>
              <hr />
              <div className="kvm-storage-cards__meter">
                <div>
                  <p className="p-heading--small u-text--light">Type</p>
                  <div>{pool.backend}</div>
                </div>
                <KVMResourceMeter
                  allocated={pool.allocated_tracked}
                  detailed
                  free={calcFreePoolStorage(pool)}
                  other={pool.allocated_other}
                  unit="B"
                />
              </div>
            </Card>
          );
        })}
      </div>
      {canBeTruncated && (
        <div className="u-align--center">
          <Button
            appearance="base"
            data-testid="show-more-pools"
            hasIcon
            onClick={() => {
              setExpanded(!expanded);
              sendAnalytics(
                "KVM details",
                "Toggle expanded storage pools",
                expanded ? "Show less storage pools" : "Show more storage pools"
              );
            }}
          >
            {expanded ? (
              <>
                <span>Show less storage pools</span>
                <Icon name="chevron-up" />
              </>
            ) : (
              <>
                <span>
                  {pluralize(
                    "more storage pool",
                    sortedPools.length - TRUNCATION_POINT,
                    true
                  )}
                </span>
                <Icon name="chevron-down" />
              </>
            )}
          </Button>
        </div>
      )}
    </>
  );
};

export default KVMStorageCards;
