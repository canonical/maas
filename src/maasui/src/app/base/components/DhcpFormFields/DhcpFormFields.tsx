import {
  Spinner,
  Notification as NotificationBanner,
  Select,
  Textarea,
} from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import MachineSelect from "./MachineSelect/MachineSelect";

import type { DHCPFormValues } from "@/app/base/components/DhcpForm/types";
import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller } from "@/app/store/controller/types";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device } from "@/app/store/device/types";
import ipRangeSelectors from "@/app/store/iprange/selectors";
import type { IPRange } from "@/app/store/iprange/types";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";

type Option = { label: string; value: string };

type ModelType = Controller | Device | IPRange | Machine | Subnet;

type Props = {
  editing: boolean;
};

const modelTypeLabel: Record<Exclude<DHCPFormValues["type"], "">, string> = {
  controller: "controller",
  device: "device",
  machine: "machine",
  subnet: "subnet",
  iprange: "IP range",
};

const generateOptions = (
  type: Exclude<DHCPFormValues["type"], "">,
  models: ModelType[] | null
): Option[] | null =>
  !!models
    ? [
        {
          value: "",
          label: `Choose ${modelTypeLabel[type]}`,
        },
      ].concat(
        models.map((model) => ({
          value:
            type === "subnet" || type === "iprange"
              ? model.id.toString()
              : ("system_id" in model && model.system_id) || "",
          label:
            type === "iprange" && "start_ip" in model
              ? `${model?.start_ip} - ${model?.end_ip}`
              : type === "subnet"
                ? ("name" in model && model.name) || ""
                : ("fqdn" in model && model.fqdn) || "",
        }))
      )
    : null;

export enum Labels {
  Description = "Description",
  Disabled = "This snippet is disabled and will not be used by MAAS.",
  Enabled = "Enabled",
  AppliesTo = "Applies to",
  LoadingData = "Loading DHCP snippet data",
  Name = "Snippet name",
  Type = "Type",
  Value = "DHCP snippet",
}

export const DhcpFormFields = ({ editing }: Props): React.ReactElement => {
  const formikProps = useFormikContext<DHCPFormValues>();
  const subnets = useSelector(subnetSelectors.all);
  const controllers = useSelector(controllerSelectors.all);
  const devices = useSelector(deviceSelectors.all);
  const machines = useSelector(machineSelectors.all);
  const ipRanges = useSelector(ipRangeSelectors.all);
  const subnetLoading = useSelector(subnetSelectors.loading);
  const subnetLoaded = useSelector(subnetSelectors.loaded);
  const controllerLoading = useSelector(controllerSelectors.loading);
  const controllerLoaded = useSelector(controllerSelectors.loaded);
  const deviceLoading = useSelector(deviceSelectors.loading);
  const deviceLoaded = useSelector(deviceSelectors.loaded);
  const ipRangesLoading = useSelector(ipRangeSelectors.loading);
  const ipRangesLoaded = useSelector(ipRangeSelectors.loaded);
  const isLoading =
    subnetLoading || controllerLoading || deviceLoading || ipRangesLoading;
  const hasLoaded =
    subnetLoaded && controllerLoaded && deviceLoaded && ipRangesLoaded;
  const { enabled, type } = formikProps.values;
  let models: ModelType[] | null;
  switch (type) {
    case "subnet":
      models = subnets;
      break;
    case "controller":
      models = controllers;
      break;
    case "machine":
      models = machines;
      break;
    case "device":
      models = devices;
      break;
    case "iprange":
      models = ipRanges;
      break;
    default:
      models = null;
  }
  return (
    <>
      {editing && !enabled && (
        <NotificationBanner severity="caution" title="Warning:">
          {Labels.Disabled}
        </NotificationBanner>
      )}
      <FormikField
        label={Labels.Name}
        name="name"
        required={true}
        type="text"
      />
      <FormikField label={Labels.Enabled} name="enabled" type="checkbox" />
      <FormikField
        component={Textarea}
        label={Labels.Description}
        name="description"
      />
      <FormikField
        component={Select}
        label={Labels.Type}
        name="type"
        onChange={(e: React.FormEvent) => {
          formikProps.handleChange(e);
          formikProps.setFieldValue("entity", "").catch((reason: unknown) => {
            throw new FormikFieldChangeError(
              "entity",
              "setFieldValue",
              reason as string
            );
          });
          formikProps
            .setFieldTouched("entity", false, false)
            .catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "entity",
                "setFieldTouched",
                reason as string
              );
            });
        }}
        options={[
          { value: "", label: "Global" },
          { value: "subnet", label: "Subnet" },
          { value: "controller", label: "Controller" },
          { value: "machine", label: "Machine" },
          { value: "device", label: "Device" },
          { value: "iprange", label: "IP Range" },
        ]}
      />
      {type === "machine" ? (
        <FormikField component={MachineSelect} name="entity" />
      ) : (
        type &&
        (isLoading || !hasLoaded ? (
          <Spinner aria-label={Labels.LoadingData} text="loading..." />
        ) : (
          <FormikField
            component={Select}
            label={Labels.AppliesTo}
            name="entity"
            options={generateOptions(type, models)}
          />
        ))
      )}
      <FormikField
        component={Textarea}
        grow
        label={Labels.Value}
        name="value"
        placeholder="Custom DHCP snippet"
        required
      />
    </>
  );
};

export default DhcpFormFields;
