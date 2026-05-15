import type { ReactElement } from "react";
import { useCallback, useState } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import BondFormFields from "../BondForm/BondFormFields";
import ToggleMembers from "../BondForm/ToggleMembers";
import type { BondFormValues } from "../BondForm/types";
import { LinkMonitoring, MacSource } from "../BondForm/types";
import {
  getParentIds,
  getValidNics,
  prepareBondPayload,
} from "../BondForm/utils";
import InterfaceFormTable from "../InterfaceFormTable";
import { networkFieldsSchema } from "../NetworkFields/NetworkFields";

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
import type { MachineDetails } from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type {
  NetworkInterface,
  NetworkLink,
  UpdateInterfaceParams,
} from "@/app/store/types/node";
import {
  getInterfaceIPAddress,
  getInterfaceSubnet,
  getLinkMode,
} from "@/app/store/utils";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import { arrayItemsEqual } from "@/app/utils";

type EditBondProps = {
  link?: NetworkLink | null;
  nic?: NetworkInterface | null;
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

const EditBondForm = ({
  link,
  nic,
  selected: _selected,
  setSelected: setParentSelected,
  systemId,
}: EditBondProps): ReactElement | null => {
  const [editingMembers, setEditingMembers] = useState(false);
  // Local state is required because `selected` is frozen in the side panel context when the panel opens and won't reflect parent updates.
  // Initialise directly from the bond's parents so the table is populated regardless of the network table selection.
  const [selected, setLocalSelected] = useState<Selected[]>(
    () => nic?.parents.map((id) => ({ nicId: id })) ?? []
  );
  const setSelected: SetSelected = useCallback(
    (newSelected) => {
      setLocalSelected(newSelected);
      setParentSelected(newSelected);
    },
    [setParentSelected]
  );
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, nic?.vlan_id)
  );
  const fabrics = useSelector(fabricSelectors.all);
  const fabricsLoaded = useSelector(fabricSelectors.loaded);
  const subnets = useSelector(subnetSelectors.all);
  const subnetsLoaded = useSelector(subnetSelectors.loaded);
  const vlans = useSelector(vlanSelectors.all);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  const cleanup = useCallback(() => machineActions.cleanup(), []);
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(machine);
  const hasEnoughNics = selected.length > 1;
  const closeForm = () => {
    closeSidePanel();
    setSelected([]);
  };
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "updatingInterface",
    "updateInterface",
    () => {
      closeForm();
    }
  );

  useFetchActions([
    fabricActions.fetch,
    subnetActions.fetch,
    vlanActions.fetch,
  ]);

  if (
    !nic ||
    !isMachineDetails(machine) ||
    !vlansLoaded ||
    !fabricsLoaded ||
    !subnetsLoaded
  ) {
    return <Spinner />;
  }
  const subnet = getInterfaceSubnet(
    machine,
    subnets,
    fabrics,
    vlans,
    isAllNetworkingDisabled,
    nic,
    link
  );
  const validNics = getValidNics(machine, vlan?.id, nic);

  // When editing the bond members then display all valid nics, otherwise just
  // show the selected nics.
  const rows = editingMembers
    ? validNics.map(({ id, links }) => ({ nicId: id, linkId: links[0]?.id }))
    : selected;
  const ipAddress = getInterfaceIPAddress(machine, fabrics, vlans, nic, link);
  const linkMonitoring =
    nic.params?.bond_downdelay ||
    nic.params?.bond_updelay ||
    nic.params?.bond_miimon
      ? LinkMonitoring.MII
      : "";
  const selectedIds = getParentIds(selected);
  const membersHaveChanged = !arrayItemsEqual(selectedIds, nic.parents);
  const macAddress = nic.mac_address || "";
  return (
    <FormikForm<BondFormValues, MachineEventErrors>
      allowUnchanged={membersHaveChanged}
      cleanup={cleanup}
      errors={errors}
      initialValues={{
        bond_downdelay: nic.params?.bond_downdelay || 0,
        bond_lacp_rate: nic.params?.bond_lacp_rate || "",
        bond_miimon: nic.params?.bond_miimon || 0,
        bond_mode: nic.params?.bond_mode || BondMode.ACTIVE_BACKUP,
        bond_updelay: nic.params?.bond_updelay || 0,
        bond_xmit_hash_policy: nic.params?.bond_xmit_hash_policy || "",
        fabric: vlan?.fabric,
        ip_address: ipAddress || "",
        linkMonitoring,
        mac_address: macAddress,
        macSource: MacSource.MANUAL,
        macNic: macAddress,
        mode: getLinkMode(link),
        name: nic.name,
        subnet: subnet?.id,
        tags: nic.tags,
        vlan: nic.vlan_id,
      }}
      onCancel={closeForm}
      onSaveAnalytics={{
        action: "Save bond",
        category: "Machine details networking",
        label: "Edit bond form",
      }}
      onSubmit={(values) => {
        // Clear the errors from the previous submission.
        dispatch(cleanup());
        const payload = prepareBondPayload(
          values,
          selected,
          systemId,
          nic,
          link
        );
        if (payload.interface_id !== undefined) {
          dispatch(
            machineActions.updateInterface({
              ...payload,
              interface_id: payload.interface_id,
            } as UpdateInterfaceParams)
          );
        }
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

export default EditBondForm;
