import type { ReactElement } from "react";
import { useCallback, useEffect, useState } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import BondFormFields from "../BondForm/BondFormFields";
import ToggleMembers from "../BondForm/ToggleMembers";
import type { BondFormValues } from "../BondForm/types";
import { MacSource } from "../BondForm/types";
import {
  getFirstSelected,
  getValidNics,
  prepareBondPayload,
} from "../BondForm/utils";
import InterfaceFormTable from "../InterfaceFormTable";
import {
  networkFieldsInitialValues,
  networkFieldsSchema,
} from "../NetworkFields/NetworkFields";

import FormikForm from "@/app/base/components/FormikForm";
import type {
  Selected,
  SetSelected,
} from "@/app/base/components/node/networking/types";
import { useFetchActions, useIsAllNetworkingDisabled } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { MAC_ADDRESS_REGEX } from "@/app/base/validation";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import {
  BondLacpRate,
  BondMode,
  BondXmitHashPolicy,
} from "@/app/store/general/types";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type {
  CreateBondParams,
  MachineDetails,
} from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkInterface } from "@/app/store/types/node";
import {
  getInterfaceSubnet,
  getLinkFromNic,
  getNextNicName,
} from "@/app/store/utils";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";

type AddBondProps = {
  selected: Selected[];
  setSelected: SetSelected;
  systemId: MachineDetails["system_id"];
};

const InterfaceSchema = Yup.object().shape({
  ...networkFieldsSchema,
  bond_downdelay: Yup.number(),
  bond_lacp_rate: Yup.mixed().oneOf(Object.values(BondLacpRate)),
  bond_miimon: Yup.number(),
  bond_mode: Yup.mixed()
    .oneOf(Object.values(BondMode))
    .required("Bond mode is required"),
  bond_updelay: Yup.number(),
  bond_xmit_hash_policy: Yup.mixed().oneOf(Object.values(BondXmitHashPolicy)),
  mac_address: Yup.string().matches(MAC_ADDRESS_REGEX, "Invalid MAC address"),
  name: Yup.string(),
  tags: Yup.array().of(Yup.string()),
});

// TODO: better prop typing, these are sometimes undefined
const AddBondForm = ({
  selected: initialSelected,
  setSelected: setParentSelected,
  systemId,
}: AddBondProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  // Local state is required because `selected` is frozen in the side panel context when the panel opens and won't reflect parent updates.
  const [selected, setLocalSelected] = useState<Selected[]>(initialSelected);
  const setSelected: SetSelected = useCallback(
    (newSelected) => {
      setLocalSelected(newSelected);
      setParentSelected(newSelected);
    },
    [setParentSelected]
  );
  const [editingMembers, setEditingMembers] = useState(false);
  const [bondVLAN, setBondVLAN] = useState<NetworkInterface["vlan_id"] | null>(
    null
  );
  const dispatch = useDispatch();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const handleClose = () => {
    setSelected([]);
    closeSidePanel();
  };
  // Use the first selected interface as the canary for the fabric and VLAN.
  const firstSelected = machine ? getFirstSelected(machine, selected) : null;
  const firstNic = useSelector((state: RootState) =>
    machineSelectors.getInterfaceById(
      state,
      systemId,
      firstSelected?.nicId,
      firstSelected?.linkId
    )
  );
  const firstLink = getLinkFromNic(firstNic, firstSelected?.linkId);
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, bondVLAN || firstNic?.vlan_id)
  );
  const fabrics = useSelector(fabricSelectors.all);
  const fabricsLoaded = useSelector(fabricSelectors.loaded);
  const subnets = useSelector(subnetSelectors.all);
  const subnetsLoaded = useSelector(subnetSelectors.loaded);
  const vlans = useSelector(vlanSelectors.all);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  const cleanup = useCallback(() => machineActions.cleanup(), []);
  const nextName = getNextNicName(machine, NetworkInterfaceTypes.BOND);
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(machine);
  const hasEnoughNics = selected.length > 1;
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "creatingBond",
    "createBond",
    () => {
      handleClose();
    }
  );

  useFetchActions([
    fabricActions.fetch,
    subnetActions.fetch,
    vlanActions.fetch,
  ]);

  useEffect(() => {
    // When the form is first shown then store the VLAN for this bond. This needs
    // to be done so that if all interfaces become deselected then the VLAN
    // information is not lost.
    if (!bondVLAN && hasEnoughNics && firstNic) {
      setBondVLAN(firstNic.vlan_id);
    }
  }, [bondVLAN, firstNic, hasEnoughNics, setBondVLAN]);

  if (
    !isMachineDetails(machine) ||
    !vlansLoaded ||
    !fabricsLoaded ||
    !subnetsLoaded ||
    !bondVLAN
  ) {
    return <Spinner data-testid="data-loading" />;
  }
  const subnet = getInterfaceSubnet(
    machine,
    subnets,
    fabrics,
    vlans,
    isAllNetworkingDisabled,
    firstNic,
    firstLink
  );
  const validNics = getValidNics(machine, vlan?.id);
  // When editing the bond members then display all valid nics, otherwise just
  // show the selected nics.
  const rows = editingMembers
    ? validNics.map(({ id, links }) => ({ nicId: id, linkId: links[0]?.id }))
    : selected;
  const macAddress = firstNic?.mac_address || "";
  return (
    <FormikForm<BondFormValues, MachineEventErrors>
      allowUnchanged
      aria-label="Create bond"
      cleanup={cleanup}
      errors={errors}
      initialValues={{
        ...networkFieldsInitialValues,
        bond_downdelay: 0,
        bond_lacp_rate: "",
        bond_mode: BondMode.ACTIVE_BACKUP,
        bond_miimon: 0,
        bond_updelay: 0,
        bond_xmit_hash_policy: "",
        fabric: vlan?.fabric,
        linkMonitoring: "",
        mac_address: macAddress,
        name: nextName || "",
        macSource: MacSource.NIC,
        macNic: macAddress,
        subnet: subnet?.id,
        tags: [],
        vlan: bondVLAN,
      }}
      onCancel={handleClose}
      onSaveAnalytics={{
        action: "Create bond",
        category: "Machine details networking",
        label: "Create bond form",
      }}
      onSubmit={(values) => {
        // Clear the errors from the previous submission.
        dispatch(cleanup());
        const payload = prepareBondPayload(
          values,
          selected,
          systemId
        ) as CreateBondParams;
        dispatch(machineActions.createBond(payload));
      }}
      resetOnSave
      saved={saved}
      saving={saving}
      submitDisabled={!hasEnoughNics}
      submitLabel="Save interface"
      validationSchema={InterfaceSchema}
    >
      <InterfaceFormTable
        interfaces={rows}
        selected={selected}
        selectedEditable={editingMembers}
        setSelected={setSelected}
        systemId={systemId}
      />
      <ToggleMembers
        editingMembers={editingMembers}
        selected={selected}
        setEditingMembers={setEditingMembers}
        validNics={validNics}
      />
      <BondFormFields selected={selected} systemId={systemId} />
    </FormikForm>
  );
};

export default AddBondForm;
