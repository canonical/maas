import type { ReactElement } from "react";
import { useCallback } from "react";

import { Spinner } from "@canonical/react-components";
import * as ipaddr from "ipaddr.js";
import { isIP, isIPv4 } from "is-ip";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import { networkFieldsSchema } from "../NetworkFields/NetworkFields";

import EditPhysicalFields from "./EditPhysicalFields";
import type { EditPhysicalValues } from "./types";

import FormikForm from "@/app/base/components/FormikForm";
import { formatIpAddress } from "@/app/base/components/PrefixedIpInput";
import { useFetchActions, useIsAllNetworkingDisabled } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { MAC_ADDRESS_REGEX } from "@/app/base/validation";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine, MachineDetails } from "@/app/store/machine/types";
import type { MachineEventErrors } from "@/app/store/machine/types/base";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import { NetworkLinkMode } from "@/app/store/types/enum";
import type {
  NetworkInterface,
  NetworkLink,
  UpdateInterfaceParams,
} from "@/app/store/types/node";
import {
  getInterfaceIPAddress,
  getInterfaceSubnet,
  getLinkFromNic,
  getLinkMode,
} from "@/app/store/utils";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import { preparePayload } from "@/app/utils";
import {
  getImmutableAndEditableOctets,
  getIpRangeFromCidr,
  isIpInSubnet,
} from "@/app/utils/subnetIpRange";

type EditPhysicalProps = {
  linkId?: NetworkLink["id"] | null;
  nicId?: NetworkInterface["id"] | null;
  systemId: MachineDetails["system_id"];
};

const InterfaceSchema = Yup.object().shape({
  ...networkFieldsSchema,
  interface_speed: Yup.number().nullable(),
  link_speed: Yup.number().nullable(),
  mac_address: Yup.string()
    .matches(MAC_ADDRESS_REGEX, "Invalid MAC address")
    .required("MAC address is required"),
  name: Yup.string(),
  tags: Yup.array().of(Yup.string()),
  ip_address: Yup.string().when("mode", {
    is: NetworkLinkMode.STATIC,
    then: Yup.string()
      .test({
        name: "ip-is-valid",
        message: "This is not a valid IP address",
        test: (ip_address, context) => {
          // Wrap this in a try/catch since the subnet might not be loaded yet
          try {
            return isIP(
              formatIpAddress(ip_address, context.parent.subnet_cidr as string)
            );
          } catch {
            return false;
          }
        },
      })
      .test({
        name: "ip-is-in-subnet",
        message: "The IP address is outside of the subnet's range.",
        test: (ip_address, context) => {
          // Wrap this in a try/catch since the subnet might not be loaded yet
          try {
            const cidr: string = context.parent.subnet_cidr;
            const networkAddress = cidr.split("/")[0];
            const prefixLength = parseInt(cidr.split("/")[1]);
            const subnetIsIpv4 = isIPv4(networkAddress);

            const ip = formatIpAddress(ip_address, cidr);
            if (subnetIsIpv4) {
              return isIpInSubnet(ip, cidr);
            } else {
              try {
                const addr = ipaddr.parse(ip);
                const netAddr = ipaddr.parse(networkAddress);
                return addr.match(netAddr, prefixLength);
              } catch {
                return false;
              }
            }
          } catch {
            return false;
          }
        },
      }),
  }),
});

const EditPhysicalForm = ({
  linkId,
  nicId,
  systemId,
}: EditPhysicalProps): ReactElement | null => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const cleanup = useCallback(() => machineActions.cleanup(), []);
  const nic = useSelector((state: RootState) =>
    machineSelectors.getInterfaceById(state, systemId, nicId, linkId)
  );
  const link = getLinkFromNic(nic, linkId);
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, nic?.vlan_id)
  );
  const fabrics = useSelector(fabricSelectors.all);
  const subnets = useSelector(subnetSelectors.all);
  const vlans = useSelector(vlanSelectors.all);
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

  if (!isMachineDetails(machine) || !nic) {
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
  const ipAddress = getInterfaceIPAddress(machine, fabrics, vlans, nic, link);

  const getInitialIpAddressValue = () => {
    if (subnet && ipAddress) {
      const [startIp, endIp] = getIpRangeFromCidr(subnet.cidr);
      const [immutableOctets, _] = getImmutableAndEditableOctets(
        startIp,
        endIp
      );
      const networkAddress = subnet.cidr.split("/")[0];
      const ipv6Prefix = networkAddress.substring(
        0,
        networkAddress.lastIndexOf(":")
      );
      const subnetIsIpv4 = isIPv4(networkAddress);

      if (subnetIsIpv4) {
        return ipAddress.replace(`${immutableOctets}.`, "");
      } else {
        return ipAddress.replace(`${ipv6Prefix}`, "");
      }
    } else {
      return "";
    }
  };

  return (
    <FormikForm<EditPhysicalValues, MachineEventErrors>
      aria-label="Edit physical"
      cleanup={cleanup}
      errors={errors}
      initialValues={{
        fabric: vlan?.fabric,
        // Convert the speeds to GB.
        interface_speed: isNaN(Number(nic.interface_speed))
          ? 0
          : nic.interface_speed / 1000,
        ip_address: getInitialIpAddressValue(),
        // The current link is required to update the subnet and ip address.
        link_id: linkId || "",
        link_speed: isNaN(Number(nic.link_speed)) ? 0 : nic.link_speed / 1000,
        mac_address: nic.mac_address,
        mode: getLinkMode(link),
        name: nic.name,
        subnet: subnet?.id,
        subnet_cidr: subnet?.cidr || "",
        tags: nic.tags,
        vlan: nic.vlan_id,
      }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Save physical interface",
        category: "Machine details networking",
        label: "Edit physical interface form",
      }}
      onSubmit={(values) => {
        // Clear the errors from the previous submission.
        dispatch(cleanup());

        const ip =
          values.ip_address && values.subnet_cidr
            ? formatIpAddress(values.ip_address, values.subnet_cidr)
            : "";
        type Payload = EditPhysicalValues & {
          interface_id: NetworkInterface["id"];
          system_id: Machine["system_id"];
        };
        const payload: Payload = preparePayload(
          {
            ...values,
            interface_id: nic.id,
            system_id: systemId,
            ip_address: ip,
          },
          [],
          ["subnet_cidr"]
        );
        // Convert the speeds back from GB.
        if (!isNaN(Number(payload.link_speed))) {
          payload.link_speed = Number(payload.link_speed) * 1000;
        }
        if (!isNaN(Number(payload.interface_speed))) {
          payload.interface_speed = Number(payload.interface_speed) * 1000;
        }
        dispatch(
          machineActions.updateInterface(payload as UpdateInterfaceParams)
        );
      }}
      resetOnSave
      saved={saved}
      saving={saving}
      submitLabel="Save interface"
      validationSchema={InterfaceSchema}
    >
      <EditPhysicalFields nic={nic} />
    </FormikForm>
  );
};

export default EditPhysicalForm;
