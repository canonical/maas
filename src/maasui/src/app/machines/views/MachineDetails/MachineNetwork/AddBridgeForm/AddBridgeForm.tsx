import type { ReactElement } from "react";
import { useEffect, useState, useCallback } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import BridgeFormFields from "../BridgeFormFields";
import InterfaceFormTable from "../InterfaceFormTable";
import {
  networkFieldsInitialValues,
  networkFieldsSchema,
} from "../NetworkFields/NetworkFields";

import type { BridgeFormValues } from "./types";

import FormikForm from "@/app/base/components/FormikForm";
import type {
  Selected,
  SetSelected,
} from "@/app/base/components/node/networking/types";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { MAC_ADDRESS_REGEX } from "@/app/base/validation";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import {
  getFirstSelected,
  getParentIds,
} from "@/app/machines/views/MachineDetails/MachineNetwork/BondForm/utils";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type {
  CreateBridgeParams,
  MachineDetails,
} from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { BridgeType, NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkInterface } from "@/app/store/types/node";
import { getNextNicName } from "@/app/store/utils";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import { preparePayload } from "@/app/utils";

const InterfaceSchema = Yup.object().shape({
  ...networkFieldsSchema,
  bridge_fd: Yup.number(),
  bridge_stp: Yup.boolean(),
  bridge_type: Yup.string().required("Bridge type is required"),
  mac_address: Yup.string()
    .matches(MAC_ADDRESS_REGEX, "Invalid MAC address")
    .required("MAC address is required"),
  name: Yup.string(),
  tags: Yup.array().of(Yup.string()),
});

type AddBridgeProps = {
  selected: Selected[];
  systemId: MachineDetails["system_id"];
  setSelected: SetSelected;
};

const AddBridgeForm = ({
  selected,
  systemId,
  setSelected,
}: AddBridgeProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const cleanup = useCallback(() => machineActions.cleanup(), []);
  const handleClose = () => {
    setSelected([]);
    closeSidePanel();
  };
  const nextName = getNextNicName(machine, NetworkInterfaceTypes.BRIDGE);
  const [bridgeVLAN, setBridgeVLAN] = useState<
    NetworkInterface["vlan_id"] | null
  >(null);
  const firstSelected = machine ? getFirstSelected(machine, selected) : null;
  const firstNic = useSelector((state: RootState) =>
    machineSelectors.getInterfaceById(
      state,
      systemId,
      firstSelected?.nicId,
      firstSelected?.linkId
    )
  );
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, bridgeVLAN || firstNic?.vlan_id)
  );
  const vlansLoading = useSelector(vlanSelectors.loading);
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "creatingBridge",
    "createBridge",
    () => {
      handleClose();
    }
  );

  useFetchActions([vlanActions.fetch]);

  useEffect(() => {
    // When the form is first shown then store the VLAN for this bridge. This needs
    // to be done so that if all interfaces become deselected then the VLAN
    // information is not lost.
    if (!bridgeVLAN && firstNic) {
      setBridgeVLAN(firstNic.vlan_id);
    }
  }, [bridgeVLAN, firstNic, setBridgeVLAN]);

  if (vlansLoading || !bridgeVLAN || !isMachineDetails(machine)) {
    return <Spinner text="Loading..." />;
  }

  const macAddress = firstNic?.mac_address || "";

  return (
    <>
      <InterfaceFormTable interfaces={selected} systemId={systemId} />
      <FormikForm<BridgeFormValues, MachineEventErrors>
        allowUnchanged
        cleanup={cleanup}
        errors={errors}
        initialValues={{
          ...networkFieldsInitialValues,
          bridge_fd: "",
          bridge_stp: false,
          bridge_type: BridgeType.STANDARD,
          // Prefill the fabric from the parent interface.
          fabric: vlan?.fabric,
          mac_address: macAddress,
          name: nextName || "",
          tags: [],
          // Prefill the vlan from the parent interface.
          vlan: bridgeVLAN,
        }}
        onCancel={handleClose}
        onSaveAnalytics={{
          action: "Create bridge",
          category: "Machine details networking",
          label: "Create bridge form",
        }}
        onSubmit={(values) => {
          // Clear the errors from the previous submission.
          dispatch(cleanup());
          const payload = preparePayload({
            ...values,
            parents: getParentIds(selected),
            system_id: systemId,
          }) as CreateBridgeParams;
          dispatch(machineActions.createBridge(payload));
        }}
        resetOnSave
        saved={saved}
        saving={saving}
        submitLabel="Save interface"
        validationSchema={InterfaceSchema}
      >
        <BridgeFormFields />
      </FormikForm>
    </>
  );
};

export default AddBridgeForm;
