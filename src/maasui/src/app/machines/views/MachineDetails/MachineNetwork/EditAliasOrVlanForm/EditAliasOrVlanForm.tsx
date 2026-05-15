import type { ReactElement } from "react";
import { useCallback } from "react";

import { Col, Row, Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import type { NetworkValues } from "../NetworkFields/NetworkFields";
import NetworkFields, {
  networkFieldsSchema,
} from "../NetworkFields/NetworkFields";

import FormikForm from "@/app/base/components/FormikForm";
import TagNameField from "@/app/base/components/TagNameField";
import { useFetchActions, useIsAllNetworkingDisabled } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type {
  NetworkInterface,
  NetworkLink,
  UpdateInterfaceParams,
} from "@/app/store/types/node";
import {
  getInterfaceIPAddress,
  getInterfaceSubnet,
  getInterfaceTypeText,
  getLinkMode,
} from "@/app/store/utils";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import { preparePayload } from "@/app/utils";

type EditAliasOrVlanProps = {
  nic?: NetworkInterface | null;
  link?: NetworkLink | null;
  interfaceType: NetworkInterfaceTypes.ALIAS | NetworkInterfaceTypes.VLAN;
  systemId: MachineDetails["system_id"];
};

export type EditAliasOrVlanValues = NetworkValues & {
  tags?: NetworkInterface["tags"];
};

const AliasOrVlanSchema = Yup.object().shape({
  ...networkFieldsSchema,
  tags: Yup.array().of(Yup.string()),
});

const EditAliasOrVlanForm = ({
  interfaceType,
  link,
  nic,
  systemId,
}: EditAliasOrVlanProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, nic?.vlan_id)
  );
  const fabrics = useSelector(fabricSelectors.all);
  const subnets = useSelector(subnetSelectors.all);
  const vlans = useSelector(vlanSelectors.all);
  const cleanup = useCallback(() => machineActions.cleanup(), []);
  const isAlias = interfaceType === NetworkInterfaceTypes.ALIAS;
  const isVLAN = interfaceType === NetworkInterfaceTypes.VLAN;
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(machine);
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "updatingInterface",
    "updateInterface",
    () => {
      closeSidePanel();
    }
  );

  useFetchActions([
    fabricActions.fetch,
    subnetActions.fetch,
    vlanActions.fetch,
  ]);

  if (!nic || !isMachineDetails(machine)) {
    return <Spinner text="Loading..." />;
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
  const ipAddress = getInterfaceIPAddress(machine, fabrics, vlans, nic, link);
  const interfaceTypeDisplay = getInterfaceTypeText(machine, nic, link);
  return (
    <FormikForm<EditAliasOrVlanValues, MachineEventErrors>
      aria-label={isAlias ? "Edit alias" : "Edit VLAN"}
      cleanup={cleanup}
      errors={errors}
      initialValues={{
        fabric: vlan?.fabric,
        ip_address: ipAddress || "",
        mode: getLinkMode(link),
        subnet: subnet?.id,
        vlan: nic.vlan_id,
        ...(isVLAN ? { tags: nic.tags } : {}),
      }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: `Save ${interfaceType}`,
        category: "Machine details networking",
        label: `Edit ${interfaceType} form`,
      }}
      onSubmit={(values) => {
        // Clear the errors from the previous submission.
        dispatch(cleanup());
        const payload = preparePayload({
          ...values,
          interface_id: nic.id,
          link_id: link?.id,
          system_id: systemId,
        }) as UpdateInterfaceParams;
        dispatch(machineActions.updateInterface(payload));
      }}
      resetOnSave
      saved={saved}
      saving={saving}
      submitLabel={`Save ${interfaceTypeDisplay}`}
      validationSchema={AliasOrVlanSchema}
    >
      <Row>
        {isVLAN ? (
          <Col size={12}>
            <h3 className="p-heading--5 u-no-margin--bottom">VLAN details</h3>
            <TagNameField />
          </Col>
        ) : null}
        <Col size={12}>
          <h3 className="p-heading--5 u-no-margin--bottom">Network</h3>
          <NetworkFields
            fabricDisabled={true}
            includeDefaultVlan={!isVLAN}
            includeUnconfiguredSubnet={isVLAN}
            interfaceType={interfaceType}
            vlanDisabled={isAlias}
          />
        </Col>
      </Row>
    </FormikForm>
  );
};

export default EditAliasOrVlanForm;
