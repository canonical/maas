import { useState } from "react";

import { Col, Row, Spinner, Strip } from "@canonical/react-components";
import ipaddr from "ipaddr.js";
import { isIP, isIPv4 } from "is-ip";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import AddDeviceInterfaces from "./AddDeviceInterfaces";
import type { AddDeviceValues } from "./types";

import { useZones } from "@/app/api/query/zones";
import DomainSelect from "@/app/base/components/DomainSelect";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { formatIpAddress } from "@/app/base/components/PrefixedIpInput";
import ZoneSelect from "@/app/base/components/ZoneSelect";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { hostnameValidation, MAC_ADDRESS_REGEX } from "@/app/base/validation";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import { DeviceIpAssignment } from "@/app/store/device/types";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import { isIpInSubnet } from "@/app/utils/subnetIpRange";

const AddDeviceInterfaceSchema = Yup.object().shape({
  mac: Yup.string()
    .matches(MAC_ADDRESS_REGEX, "Invalid MAC address")
    .required("MAC address is required"),
  ip_assignment: Yup.string().required("IP assignment is required"),
  ip_address: Yup.string()
    .when("ip_assignment", {
      is: (ipAssignment: DeviceIpAssignment) =>
        ipAssignment === DeviceIpAssignment.STATIC,
      then: Yup.string()
        .test({
          name: "ip-is-valid",
          message: "This is not a valid IP address",
          test: (ip_address, context) => {
            // Wrap this in a try/catch since the subnet might not be loaded yet
            try {
              return isIP(
                formatIpAddress(
                  ip_address,
                  context.parent.subnet_cidr as string
                )
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
    })
    .when("ip_assignment", {
      is: (ipAssignment: DeviceIpAssignment) =>
        ipAssignment === DeviceIpAssignment.EXTERNAL,
      then: Yup.string().test({
        name: "ip-is-valid",
        message: "This is not a valid IP address",
        test: (ip_address) => isIP(`${ip_address}`),
      }),
    })
    .when("ip_assignment", {
      is: (ipAssignment: DeviceIpAssignment) =>
        ipAssignment === DeviceIpAssignment.STATIC ||
        ipAssignment === DeviceIpAssignment.EXTERNAL,
      then: Yup.string().required("IP address is required"),
    }),
  subnet: Yup.number().when("ip_assignment", {
    is: (ipAssignment: DeviceIpAssignment) =>
      ipAssignment === DeviceIpAssignment.STATIC,
    then: Yup.number().required("Subnet is required"),
  }),
  subnet_cidr: Yup.string(),
});

const AddDeviceSchema = Yup.object().shape({
  domain: Yup.string().required("Domain required"),
  hostname: hostnameValidation,
  interfaces: Yup.array()
    .of(AddDeviceInterfaceSchema)
    .min(1, "At least one interface must be defined"),
  zone: Yup.string().required("Zone required"),
});

export const AddDeviceForm = (): React.ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const devicesSaved = useSelector(deviceSelectors.saved);
  const devicesSaving = useSelector(deviceSelectors.saving);
  const devicesErrors = useSelector(deviceSelectors.errors);
  const domains = useSelector(domainSelectors.all);
  const domainsLoaded = useSelector(domainSelectors.loaded);
  const subnetsLoaded = useSelector(subnetSelectors.loaded);
  const zones = useZones();

  const [secondarySubmit, setSecondarySubmit] = useState(false);

  // Fetch all data required for the form.
  useFetchActions([domainActions.fetch, subnetActions.fetch]);

  const loaded = domainsLoaded && subnetsLoaded && !zones.isPending;

  if (!loaded) {
    return (
      <Strip>
        <Spinner text="Loading" />
      </Strip>
    );
  }

  return (
    <FormikForm<AddDeviceValues>
      aria-label="Add device"
      cleanup={deviceActions.cleanup}
      errors={devicesErrors}
      initialValues={{
        domain: (domains.length && domains[0].name) || "",
        hostname: "",
        interfaces: [
          {
            id: 0,
            ip_address: "",
            ip_assignment: DeviceIpAssignment.DYNAMIC,
            mac: "",
            name: "eth0",
            subnet: "",
            // Capture the subnet CIDR so we can validate the IP address against it.
            subnet_cidr: "",
          },
        ],
        zone: zones.data?.items.length ? zones.data.items[0].name : "",
      }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Add device",
        category: "Device list",
        label: secondarySubmit ? "Save and add another" : "Save device",
      }}
      onSubmit={(values) => {
        const { domain, hostname, interfaces, zone } = values;
        const normalisedInterfaces = interfaces.map((iface) => {
          const subnet = parseInt(iface.subnet);
          const ip =
            iface.ip_assignment === DeviceIpAssignment.STATIC
              ? formatIpAddress(iface.ip_address, iface.subnet_cidr)
              : iface.ip_assignment === DeviceIpAssignment.EXTERNAL
                ? iface.ip_address
                : null;

          // subnet_cidr is omitted, since it's only needed for validation.
          return {
            ip_address: ip || null,
            ip_assignment: iface.ip_assignment,
            mac: iface.mac,
            name: iface.name,
            subnet: subnet || subnet === 0 ? subnet : null,
          };
        });
        // We determine the MAC addresses of the device based on the defined
        // interfaces.
        const { primary_mac, extra_macs } = normalisedInterfaces.reduce<{
          primary_mac: string;
          extra_macs: string[];
        }>(
          (split, iface, i) => {
            if (i === 0) {
              split.primary_mac = iface.mac;
            } else {
              split.extra_macs.push(iface.mac);
            }
            return split;
          },
          { primary_mac: "", extra_macs: [] }
        );
        const params = {
          domain: { name: domain },
          extra_macs,
          hostname,
          interfaces: normalisedInterfaces,
          primary_mac,
          zone: { name: zone },
        };
        dispatch(deviceActions.create(params));
      }}
      onSuccess={() => {
        if (!secondarySubmit) {
          closeSidePanel();
        }
        setSecondarySubmit(false);
      }}
      resetOnSave
      saved={devicesSaved}
      saving={devicesSaving}
      secondarySubmit={(_, { submitForm }) => {
        setSecondarySubmit(true);
        return submitForm();
      }}
      secondarySubmitLabel="Save and add another"
      submitLabel="Save device"
      validationSchema={AddDeviceSchema}
    >
      <Row>
        <Col size={12}>
          <FormikField
            label="Device name"
            name="hostname"
            placeholder="Device name (optional)"
            type="text"
          />
          <DomainSelect name="domain" required />
          <ZoneSelect name="zone" required />
        </Col>
      </Row>
      <Strip shallow>
        <AddDeviceInterfaces />
      </Strip>
    </FormikForm>
  );
};

export default AddDeviceForm;
