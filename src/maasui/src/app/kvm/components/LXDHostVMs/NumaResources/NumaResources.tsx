import { useState } from "react";

import { Button, Icon, Spinner } from "@canonical/react-components";
import classNames from "classnames";
import pluralize from "pluralize";
import { useSelector } from "react-redux";

import NumaResourcesCard from "./NumaResourcesCard";

import { useSendAnalytics } from "@/app/base/hooks";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";

export const TRUNCATION_POINT = 4;

type Props = { id: Pod["id"] };

const NumaResources = ({ id }: Props): React.ReactElement => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, id)
  );
  const [expanded, setExpanded] = useState(false);
  const sendAnalytics = useSendAnalytics();

  if (!!pod) {
    const { resources } = pod;
    const numaNodes = resources.numa;
    const canBeTruncated = numaNodes.length > TRUNCATION_POINT;
    const shownNumaNodes =
      canBeTruncated && !expanded
        ? numaNodes.slice(0, TRUNCATION_POINT)
        : numaNodes;
    const showWideCards = numaNodes.length <= 2;

    return (
      <>
        <div
          className={classNames("numa-resources", {
            "is-wide": showWideCards,
          })}
          data-testid="numa-resources"
        >
          {shownNumaNodes.map((numa) => (
            <NumaResourcesCard
              key={`numa-${numa.node_id}`}
              numaId={numa.node_id}
              podId={pod.id}
            />
          ))}
        </div>
        {canBeTruncated && (
          <div className="u-align--center">
            <Button
              appearance="base"
              data-testid="show-more-numas"
              hasIcon
              onClick={() => {
                setExpanded(!expanded);
                sendAnalytics(
                  "KVM details",
                  "Toggle expanded NUMA nodes",
                  expanded ? "Show less NUMA nodes" : "Show more NUMA nodes"
                );
              }}
            >
              {expanded ? (
                <>
                  <span>Show less NUMA nodes</span>
                  <Icon name="chevron-up" />
                </>
              ) : (
                <>
                  <span>
                    {pluralize(
                      "more NUMA node",
                      numaNodes.length - TRUNCATION_POINT,
                      true
                    )}
                  </span>
                  <Icon name="chevron-down" />
                </>
              )}
            </Button>
            <hr />
          </div>
        )}
      </>
    );
  }
  return <Spinner text="Loading" />;
};

export default NumaResources;
