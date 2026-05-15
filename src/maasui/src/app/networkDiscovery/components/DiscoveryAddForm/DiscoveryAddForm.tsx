import type { ReactElement } from "react";
import { useState } from "react";

import { NotificationSeverity, Spinner } from "@canonical/react-components";
import { useQueryClient } from "@tanstack/react-query";
import { useDispatch, useSelector } from "react-redux";
import type { Dispatch } from "redux";
import * as Yup from "yup";

import DiscoveryAddFormFields from "./DiscoveryAddFormFields";
import type { DiscoveryAddValues } from "./types";
import { DeviceType } from "./types";

import type { DiscoveryResponse } from "@/app/apiclient";
import { listDiscoveriesQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";
import FormikForm from "@/app/base/components/FormikForm";
import { useCycled, useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import { hostnameValidation } from "@/app/base/validation";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type { CreateInterfaceParams, Device } from "@/app/store/device/types";
import { DeviceIpAssignment, DeviceMeta } from "@/app/store/device/types";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import { useFetchMachines } from "@/app/store/machine/utils/hooks";
import { messageActions } from "@/app/store/message";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import { FetchNodeStatus } from "@/app/store/types/node";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import { preparePayload } from "@/app/utils";

export enum Labels {
  SubmitLabel = "Save",
  SecondarySubmitParent = "Save and go to machine details",
  SecondarySubmitNoParent = "Save and go to device listing",
}

type Props = {
  discovery: DiscoveryResponse;
};

const formSubmit = (
  dispatch: Dispatch,
  discovery: DiscoveryResponse,
  values: DiscoveryAddValues
) => {
  // Clear the errors from the previous submission.
  if (values.type === DeviceType.DEVICE) {
    if (!discovery.ip || !discovery.mac_address || !discovery.subnet_id) {
      return;
    }
    dispatch(
      deviceActions.create({
        domain: { name: values.domain },
        extra_macs: [],
        hostname: values.hostname,
        interfaces: [
          {
            ip_address: discovery.ip,
            ip_assignment: values.ip_assignment,
            mac: discovery.mac_address,
            subnet: discovery.subnet_id,
          },
        ],
        parent: values.parent || "",
        primary_mac: discovery.mac_address,
      })
    );
  } else {
    dispatch(
      deviceActions.createInterface(
        preparePayload(
          {
            [DeviceMeta.PK]: values.system_id,
            ip_address: discovery.ip,
            ip_assignment: values.ip_assignment,
            mac_address: discovery.mac_address,
            name: values.hostname,
            subnet: discovery.subnet_id?.toString(),
            vlan: discovery.vlan_id,
          },
          [],
          [],
          true
        ) as CreateInterfaceParams
      )
    );
  }
};

const setRedirectURL = (
  values: DiscoveryAddValues,
  setRedirect: (redirect: string | null) => void
) => {
  setRedirect(
    values.parent
      ? urls.machines.machine.index({ id: values.parent })
      : urls.devices.index
  );
};

const DiscoveryAddSchema = Yup.object().shape({
  [DeviceMeta.PK]: Yup.string().when("type", {
    is: DeviceType.INTERFACE,
    then: Yup.string().required(
      "A device is required when adding an interface."
    ),
  }),
  domain: Yup.string(),
  hostname: hostnameValidation,
  ip_assignment: Yup.string(),
  parent: Yup.string(),
  type: Yup.string(),
});

const DiscoveryAddForm = ({ discovery }: Props): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  const dispatch = useDispatch();
  const [redirect, setRedirect] = useState<string | null>(null);
  const initialDeviceType = DeviceType.DEVICE;
  const [deviceType, setDeviceType] = useState<DeviceType>(initialDeviceType);
  const [device, setDevice] = useState<Device[DeviceMeta.PK] | null>(null);
  const devicesLoaded = useSelector(deviceSelectors.loaded);
  const defaultDomain = useSelector(domainSelectors.getDefault);
  let hostname = discovery.hostname;
  let domainName: string | null = null;
  if (hostname?.includes(".")) {
    [hostname, domainName] = hostname?.split(".");
  }
  const domainByName = useSelector((state: RootState) =>
    domainSelectors.getByName(state, domainName)
  );
  const domainsLoaded = useSelector(domainSelectors.loaded);
  let errors = useSelector(deviceSelectors.errors);
  const saved = useSelector(deviceSelectors.saved);
  const saving = useSelector(deviceSelectors.saving);
  const creatingInterface = useSelector((state: RootState) =>
    deviceSelectors.getStatusForDevice(state, device, "creatingInterface")
  );
  const creatingInterfaceErrors = useSelector((state: RootState) =>
    deviceSelectors.eventErrorsForDevices(state, device, "creatingInterface")
  );
  const subnetsLoaded = useSelector(subnetSelectors.loaded);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  const [createdInterface] = useCycled(
    !creatingInterface && creatingInterfaceErrors.length === 0
  );
  const processing =
    deviceType === DeviceType.DEVICE ? saving : creatingInterface;
  const processed = deviceType === DeviceType.DEVICE ? saved : createdInterface;
  const { loaded: machinesLoaded } = useFetchMachines({
    filters: { status: FetchNodeStatus.DEPLOYED },
  });

  const queryClient = useQueryClient();

  useFetchActions([
    deviceActions.fetch,
    domainActions.fetch,
    subnetActions.fetch,
    vlanActions.fetch,
  ]);

  if (
    !devicesLoaded ||
    !domainsLoaded ||
    !machinesLoaded ||
    !subnetsLoaded ||
    !vlansLoaded
  ) {
    return <Spinner />;
  }

  // When creating an interface the error will get returned for "name" but this
  // form uses "hostname" for the field name.
  if (errors && typeof errors === "object" && "name" in errors) {
    errors = { ...errors, hostname: errors.name };
    delete errors.name;
  }

  return (
    <FormikForm<DiscoveryAddValues>
      allowUnchanged
      aria-label="Add discovery"
      className="u-width--full"
      errors={errors}
      initialValues={{
        [DeviceMeta.PK]: "",
        domain: (domainByName || defaultDomain)?.name || "",
        hostname: hostname || "",
        ip_assignment: DeviceIpAssignment.DYNAMIC,
        parent: "",
        type: initialDeviceType,
      }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Add discovery",
        category: "Dashboard",
        label: "Add discovery form",
      }}
      onSubmit={(values) => {
        // The normal submit button should not redirect anywhere.
        setRedirect(null);
        formSubmit(dispatch, discovery, values);
      }}
      onSuccess={async (values) => {
        // Refetch the discoveries so that this discovery will get removed
        // from the list.
        await queryClient.invalidateQueries({
          queryKey: listDiscoveriesQueryKey(),
        });
        if (!redirect) {
          closeSidePanel();
          let device: string;
          if (values.hostname) {
            device = values.hostname;
          } else if (values.type === DeviceType.INTERFACE) {
            device = `An ${values.type}`;
          } else {
            device = `A ${values.type}`;
          }
          dispatch(
            messageActions.add(
              `${device} has been added.`,
              NotificationSeverity.POSITIVE
            )
          );
        }
      }}
      saved={processed}
      savedRedirect={redirect}
      saving={processing}
      secondarySubmit={(values) => {
        // The secondary submit should redirect to the device/devices.
        setRedirectURL(values, setRedirect);
        formSubmit(dispatch, discovery, values);
      }}
      secondarySubmitLabel={(values) =>
        values.parent
          ? Labels.SecondarySubmitParent
          : Labels.SecondarySubmitNoParent
      }
      submitLabel={Labels.SubmitLabel}
      validationSchema={DiscoveryAddSchema}
    >
      <DiscoveryAddFormFields
        discovery={discovery}
        setDevice={setDevice}
        setDeviceType={setDeviceType}
      />
    </FormikForm>
  );
};

export default DiscoveryAddForm;
