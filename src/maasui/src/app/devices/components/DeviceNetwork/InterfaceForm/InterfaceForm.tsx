import type { PropsWithSpread } from "@canonical/react-components";
import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import * as Yup from "yup";

import InterfaceFormFields from "./InterfaceFormFields";

import type { FormikFormProps } from "@/app/base/components/FormikForm";
import FormikForm from "@/app/base/components/FormikForm";
import { TAG_SELECTOR_INPUT_NAME } from "@/app/base/components/TagSelector/TagSelector";
import { useFetchActions, useIsAllNetworkingDisabled } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { MAC_ADDRESS_REGEX } from "@/app/base/validation";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type {
  Device,
  DeviceMeta,
  DeviceNetworkInterface,
} from "@/app/store/device/types";
import { DeviceIpAssignment } from "@/app/store/device/types";
import { isDeviceDetails } from "@/app/store/device/utils";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkLink } from "@/app/store/types/node";
import {
  getInterfaceSubnet,
  getLinkFromNic,
  getNextNicName,
} from "@/app/store/utils";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";

type Props = PropsWithSpread<
  {
    linkId?: NetworkLink["id"] | null;
    nicId?: DeviceNetworkInterface["id"] | null;
    onSubmit: FormikFormProps<InterfaceFormValues>["onSubmit"];
    showTitles?: boolean;
    systemId: Device[DeviceMeta.PK];
  },
  Partial<Omit<FormikFormProps<InterfaceFormValues>, "onSubmit">>
>;

export type InterfaceFormValues = {
  ip_address: string;
  ip_assignment: DeviceIpAssignment;
  mac_address: string;
  name: string;
  subnet: Subnet[SubnetMeta.PK] | "";
  tags: string[];
};

const InterfaceFormSchema = Yup.object().shape({
  ip_address: Yup.string().when("ip_assignment", {
    is: (ipAssignment: DeviceIpAssignment) =>
      ipAssignment === DeviceIpAssignment.STATIC ||
      ipAssignment === DeviceIpAssignment.EXTERNAL,
    then: Yup.string().required("IP address is required"),
  }),
  ip_assignment: Yup.string().required("IP assignment is required"),
  mac_address: Yup.string()
    .matches(MAC_ADDRESS_REGEX, "Invalid MAC address")
    .required("MAC address is required"),
  name: Yup.string(),
  subnet: Yup.number().when("ip_assignment", {
    is: (ipAssignment: DeviceIpAssignment) =>
      ipAssignment === DeviceIpAssignment.STATIC,
    then: Yup.number().required("Subnet is required"),
  }),
  tags: Yup.array().of(Yup.string()),
});

const InterfaceForm = ({
  linkId,
  showTitles,
  nicId,
  onSubmit,
  systemId,
  ...props
}: Props): React.ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const fabrics = useSelector(fabricSelectors.all);
  const subnets = useSelector(subnetSelectors.all);
  const vlans = useSelector(vlanSelectors.all);
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, systemId)
  );
  const nic = useSelector((state: RootState) =>
    deviceSelectors.getInterfaceById(state, systemId, nicId, linkId)
  );
  const link = getLinkFromNic(nic, linkId);
  const errors = useSelector(deviceSelectors.errors);
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(device);

  useFetchActions([
    fabricActions.fetch,
    subnetActions.fetch,
    vlanActions.fetch,
  ]);

  if (!isDeviceDetails(device)) {
    return <Spinner data-testid="loading-device-details" text="Loading..." />;
  }
  const nextName = getNextNicName(device, NetworkInterfaceTypes.PHYSICAL);
  const subnet = getInterfaceSubnet(
    device,
    subnets,
    fabrics,
    vlans,
    isAllNetworkingDisabled,
    nic,
    link
  );
  return (
    <FormikForm<InterfaceFormValues>
      cleanup={deviceActions.cleanup}
      errors={errors}
      initialValues={{
        ip_address: nic?.ip_address || "",
        ip_assignment: nic?.ip_assignment || DeviceIpAssignment.DYNAMIC,
        mac_address: nic?.mac_address || "",
        name: nic?.name || nextName || "",
        subnet: subnet?.id || "",
        tags: nic?.tags || [],
        [TAG_SELECTOR_INPUT_NAME]: "",
      }}
      onCancel={closeSidePanel}
      onSubmit={onSubmit}
      onSuccess={closeSidePanel}
      submitLabel="Save interface"
      validationSchema={InterfaceFormSchema}
      {...props}
    >
      <InterfaceFormFields showTitles={showTitles} />
    </FormikForm>
  );
};

export default InterfaceForm;
