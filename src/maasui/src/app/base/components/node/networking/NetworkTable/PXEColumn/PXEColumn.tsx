import { Icon } from "@canonical/react-components";

import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import { isBootInterface } from "@/app/store/utils";

type Props = {
  link?: NetworkLink | null;
  nic?: NetworkInterface | null;
  node: ControllerDetails | MachineDetails;
};

export enum Label {
  IsBoot = "PXE boot",
}

const PXEColumn = ({ link, nic, node }: Props): React.ReactElement | null => {
  const isBoot = isBootInterface(node, nic, link);

  return isBoot ? (
    <span aria-label={Label.IsBoot} className="u-align--center">
      <Icon name="tick" />
    </span>
  ) : null;
};

export default PXEColumn;
