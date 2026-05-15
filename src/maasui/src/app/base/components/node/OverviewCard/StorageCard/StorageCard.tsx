import type { ReactElement } from "react";

import pluralize from "pluralize";
import { Link } from "react-router";

import TestResults from "@/app/base/components/node/TestResults";
import { HardwareType } from "@/app/base/enum";
import urls from "@/app/base/urls";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { nodeIsMachine } from "@/app/store/utils";

type StorageCardProps = {
  node: ControllerDetails | MachineDetails;
};

const StorageCard = ({ node }: StorageCardProps): ReactElement => (
  <>
    <div className="overview-card__storage">
      <strong className="p-muted-heading u-flex--between u-no-margin--bottom u-no-padding--top">
        Storage
      </strong>
      <h4 className="u-no-margin--bottom">
        <span>{node.storage ? `${node.storage} GB` : "Unknown"}</span>
        {node.storage && node.physical_disk_count ? (
          <small className="u-text--muted">
            &nbsp;over {pluralize("disk", node.physical_disk_count, true)}
          </small>
        ) : null}
      </h4>
    </div>
    {nodeIsMachine(node) ? (
      <TestResults hardwareType={HardwareType.Storage} machine={node} />
    ) : (
      <div className="overview-card__storage-tests">
        <Link to={urls.controllers.controller.storage({ id: node.system_id })}>
          See storage
        </Link>
      </div>
    )}
  </>
);

export default StorageCard;
