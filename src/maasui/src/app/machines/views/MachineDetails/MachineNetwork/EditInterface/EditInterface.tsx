import type { ReactElement, ReactNode } from "react";

import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import EditAliasOrVlanForm from "../EditAliasOrVlanForm";
import EditBondForm from "../EditBondForm";
import EditBridgeForm from "../EditBridgeForm";
import EditPhysicalForm from "../EditPhysicalForm";

import type {
  Selected,
  SetSelected,
} from "@/app/base/components/node/networking/types";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import { getInterfaceType, getLinkFromNic } from "@/app/store/utils";

type EditInterfaceProps = {
  linkId?: NetworkLink["id"] | null;
  nicId?: NetworkInterface["id"] | null;
  selected: Selected[];
  setSelected: SetSelected;
  systemId: MachineDetails["system_id"];
};

const EditInterface = ({
  linkId,
  nicId,
  selected,
  setSelected,
  systemId,
}: EditInterfaceProps): ReactElement => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const nic = useSelector((state: RootState) =>
    machineSelectors.getInterfaceById(state, systemId, nicId, linkId)
  );
  const link = getLinkFromNic(nic, linkId);
  if (!isMachineDetails(machine)) {
    return <Spinner text="Loading..." />;
  }
  const interfaceType = getInterfaceType(machine, nic, link);
  let form: ReactNode;
  if (interfaceType === NetworkInterfaceTypes.PHYSICAL) {
    form = (
      <EditPhysicalForm linkId={linkId} nicId={nicId} systemId={systemId} />
    );
  } else if (
    interfaceType === NetworkInterfaceTypes.ALIAS ||
    interfaceType === NetworkInterfaceTypes.VLAN
  ) {
    form = (
      <EditAliasOrVlanForm
        interfaceType={interfaceType}
        link={link}
        nic={nic}
        systemId={systemId}
      />
    );
  } else if (interfaceType === NetworkInterfaceTypes.BRIDGE) {
    form = <EditBridgeForm link={link} nic={nic} systemId={systemId} />;
  } else if (interfaceType === NetworkInterfaceTypes.BOND) {
    form = (
      <EditBondForm
        link={link}
        nic={nic}
        selected={selected}
        setSelected={setSelected}
        systemId={systemId}
      />
    );
  }
  return <>{form}</>;
};

export default EditInterface;
