import type { ReactElement } from "react";
import { useCallback } from "react";

import { Col, Input, Row, Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import NetworkFields from "../NetworkFields";
import type { NetworkValues } from "../NetworkFields/NetworkFields";
import {
  networkFieldsInitialValues,
  networkFieldsSchema,
} from "../NetworkFields/NetworkFields";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import MacAddressField from "@/app/base/components/MacAddressField";
import TagNameField from "@/app/base/components/TagNameField";
import { useScrollOnRender } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { MAC_ADDRESS_REGEX } from "@/app/base/validation";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type {
  CreatePhysicalParams,
  MachineDetails,
} from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkInterface } from "@/app/store/types/node";
import { getNextNicName } from "@/app/store/utils";
import { preparePayload } from "@/app/utils";

type AddInterfaceProps = {
  systemId: MachineDetails["system_id"];
};

export type AddInterfaceValues = NetworkValues & {
  mac_address: NetworkInterface["mac_address"];
  name?: NetworkInterface["name"];
  tags?: NetworkInterface["tags"];
};

const InterfaceSchema = Yup.object().shape({
  ...networkFieldsSchema,
  mac_address: Yup.string()
    .matches(MAC_ADDRESS_REGEX, "Invalid MAC address")
    .required("MAC address is required"),
  name: Yup.string(),
  tags: Yup.array().of(Yup.string()),
});

const AddInterface = ({ systemId }: AddInterfaceProps): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const cleanup = useCallback(() => machineActions.cleanup(), []);
  const nextName = getNextNicName(machine, NetworkInterfaceTypes.PHYSICAL);
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    "creatingPhysical",
    "createPhysical",
    () => {
      closeSidePanel();
    }
  );
  const onRenderRef = useScrollOnRender<HTMLDivElement>();

  if (!isMachineDetails(machine)) {
    return <Spinner text="Loading..." />;
  }
  return (
    <div ref={onRenderRef}>
      <FormikForm<AddInterfaceValues, MachineEventErrors>
        cleanup={cleanup}
        errors={errors}
        initialValues={{
          ...networkFieldsInitialValues,
          mac_address: "",
          name: nextName || "",
          tags: [],
        }}
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Add interface",
          category: "Machine details networking",
          label: "Add interface form",
        }}
        onSubmit={(values) => {
          // Clear the errors from the previous submission.
          dispatch(cleanup());
          const payload = preparePayload({
            ...values,
            system_id: systemId,
          }) as CreatePhysicalParams;
          dispatch(machineActions.createPhysical(payload));
        }}
        resetOnSave
        saved={saved}
        saving={saving}
        submitLabel="Save interface"
        validateOnMount
        validationSchema={InterfaceSchema}
      >
        <Row>
          <Col size={12}>
            <FormikField label="Name" name="name" type="text" />
          </Col>
        </Row>
        <hr />
        <Row>
          <Col size={12}>
            <Input
              disabled
              label="Type"
              name="type"
              type="text"
              value="Physical"
            />
            <MacAddressField label="MAC address" name="mac_address" />
            <TagNameField />
          </Col>
          <Col size={12}>
            <NetworkFields interfaceType={NetworkInterfaceTypes.PHYSICAL} />
          </Col>
        </Row>
      </FormikForm>
    </div>
  );
};

export default AddInterface;
