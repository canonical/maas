import type { ReactElement } from "react";
import { useCallback, useState } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import {
  networkFieldsInitialValues,
  networkFieldsSchema,
} from "../NetworkFields/NetworkFields";

import AddAliasOrVlanFields from "./AddAliasOrVlanFields";
import type { AddAliasOrVlanValues } from "./types";

import FormikForm from "@/app/base/components/FormikForm";
import { useScrollOnRender } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type {
  CreateVlanParams,
  LinkSubnetParams,
  MachineDetails,
} from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkInterface } from "@/app/store/types/node";
import vlanSelectors from "@/app/store/vlan/selectors";
import { preparePayload } from "@/app/utils";

export enum Labels {
  SaveInterface = "Save interface",
  SaveAndAdd = "Save and add another",
}

type AddAliasOrVlanProps = {
  nic: NetworkInterface;
  interfaceType: NetworkInterfaceTypes.ALIAS | NetworkInterfaceTypes.VLAN;
  systemId: MachineDetails["system_id"];
};

const InterfaceSchema = Yup.object().shape({
  ...networkFieldsSchema,
  tags: Yup.array().of(Yup.string()),
});

const AddAliasOrVlan = ({
  nic,
  interfaceType,
  systemId,
}: AddAliasOrVlanProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const [secondarySubmit, setSecondarySubmit] = useState(false);
  const dispatch = useDispatch();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const unusedVLANs = useSelector((state: RootState) =>
    vlanSelectors.getUnusedForInterface(state, machine, nic)
  );
  const nicVLAN = useSelector((state: RootState) =>
    vlanSelectors.getById(state, nic.vlan_id)
  );
  const cleanup = useCallback(() => machineActions.cleanup(), []);
  const isAlias = interfaceType === NetworkInterfaceTypes.ALIAS;
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    isAlias ? "linkingSubnet" : "creatingVlan",
    isAlias ? "linkSubnet" : "createVlan",
    () => {
      if (secondarySubmit) {
        // Reset the flag for the action that submitted the form.
        setSecondarySubmit(false);
      } else {
        closeSidePanel();
      }
    }
  );
  const onRenderRef = useScrollOnRender<HTMLDivElement>();
  const canAddAnother = isAlias || (!isAlias && unusedVLANs.length > 1);

  if (!nicVLAN || !isMachineDetails(machine)) {
    return <Spinner text="Loading..." />;
  }
  return (
    <div ref={onRenderRef}>
      <FormikForm<AddAliasOrVlanValues, MachineEventErrors>
        cleanup={cleanup}
        errors={errors}
        initialValues={{
          ...networkFieldsInitialValues,
          ...(isAlias ? {} : { tags: [] }),
          fabric: nicVLAN.fabric,
          vlan: nic.vlan_id,
        }}
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: `Add ${interfaceType}`,
          category: "Machine details networking",
          label: `Add ${interfaceType} form`,
        }}
        onSubmit={(values) => {
          // Clear the errors from the previous submission.
          dispatch(cleanup());
          if (isAlias) {
            // Create an alias.
            const params = preparePayload({
              ...values,
              interface_id: nic.id,
              system_id: systemId,
            }) as LinkSubnetParams;
            if (params.mode !== undefined) {
              dispatch(machineActions.linkSubnet(params));
            }
          } else {
            // Create a VLAN.
            const params = preparePayload({
              ...values,
              parent: nic.id,
              system_id: systemId,
            }) as CreateVlanParams;
            dispatch(machineActions.createVlan(params));
          }
        }}
        resetOnSave
        saved={saved}
        saving={saving}
        secondarySubmit={(_, { submitForm }) => {
          // Flag that the form was submitted by the secondary action.
          setSecondarySubmit(true);
          return submitForm();
        }}
        secondarySubmitDisabled={!canAddAnother}
        secondarySubmitLabel={Labels.SaveAndAdd}
        secondarySubmitTooltip={
          canAddAnother
            ? null
            : "There are no more unused VLANS for this interface."
        }
        submitLabel={Labels.SaveInterface}
        validationSchema={InterfaceSchema}
      >
        <AddAliasOrVlanFields
          interfaceType={interfaceType}
          nic={nic}
          systemId={systemId}
        />
      </FormikForm>
    </div>
  );
};

export default AddAliasOrVlan;
