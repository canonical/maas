import type { ReactElement } from "react";
import { useCallback } from "react";

import { Spinner } from "@canonical/react-components";
import * as ipaddr from "ipaddr.js";
import { isIP, isIPv4 } from "is-ip";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import MacAddressField from "@/app/base/components/MacAddressField";
import PrefixedIpInput, {
  formatIpAddress,
} from "@/app/base/components/PrefixedIpInput";
import { useSidePanel } from "@/app/base/side-panel-context";
import { MAC_ADDRESS_REGEX } from "@/app/base/validation";
import { reservedIpActions } from "@/app/store/reservedip";
import reservedIpSelectors from "@/app/store/reservedip/selectors";
import type { RootState } from "@/app/store/root/types";
import subnetSelectors from "@/app/store/subnet/selectors";
import { isSubnetDetails } from "@/app/store/subnet/utils";
import {
  getImmutableAndEditableOctets,
  getIpRangeFromCidr,
  isIpInSubnet,
} from "@/app/utils/subnetIpRange";

const MAX_COMMENT_LENGTH = 255;

type ReserveDHCPLeaseProps = {
  subnetId?: number;
  reservedIpId?: number;
};

type FormValues = {
  ip_address: string;
  mac_address: string;
  comment: string;
};

const ReserveDHCPLease = ({
  subnetId,
  reservedIpId,
}: ReserveDHCPLeaseProps): ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const subnet = useSelector((state: RootState) =>
    subnetSelectors.getById(state, subnetId)
  );
  const reservedIp = useSelector((state: RootState) =>
    reservedIpSelectors.getById(state, reservedIpId)
  );
  const subnetReservedIps = useSelector((state: RootState) =>
    reservedIpSelectors.getBySubnet(state, subnetId)
  );

  const subnetReservedIpList = subnetReservedIps
    .map((reservedIp) => reservedIp.ip)
    .filter((ipAddress) => ipAddress !== reservedIp?.ip);
  const subnetUsedIps = isSubnetDetails(subnet)
    ? subnet.ip_addresses
        .map((address) => address.ip)
        .filter((ipAddress) => ipAddress !== reservedIp?.ip)
    : [];

  const subnetLoading = useSelector(subnetSelectors.loading);
  const reservedIpLoading = useSelector(reservedIpSelectors.loading);
  const errors = useSelector(reservedIpSelectors.errors);
  const saving = useSelector(reservedIpSelectors.saving);
  const saved = useSelector(reservedIpSelectors.saved);
  const dispatch = useDispatch();
  const cleanup = useCallback(() => reservedIpActions.cleanup(), []);

  const loading = subnetLoading || reservedIpLoading;
  const isEditing = !!reservedIpId;

  if (loading) {
    return <Spinner text="Loading..." />;
  }

  if (!subnet) {
    return null;
  }

  const [startIp, endIp] = getIpRangeFromCidr(subnet.cidr);
  const [immutableOctets, _] = getImmutableAndEditableOctets(startIp, endIp);
  const networkAddress = subnet.cidr.split("/")[0];
  const ipv6Prefix = networkAddress.substring(
    0,
    networkAddress.lastIndexOf(":")
  );
  const prefixLength = parseInt(subnet.cidr.split("/")[1]);
  const subnetIsIpv4 = isIPv4(networkAddress);

  const getInitialValues = () => {
    if (reservedIp && subnet) {
      return {
        ip_address: subnetIsIpv4
          ? reservedIp.ip.replace(`${immutableOctets}.`, "")
          : reservedIp.ip.replace(`${ipv6Prefix}`, ""),
        mac_address: reservedIp.mac_address || "",
        comment: reservedIp.comment || "",
      };
    } else {
      return {
        ip_address: "",
        mac_address: "",
        comment: "",
      };
    }
  };

  const ReserveDHCPLeaseSchema = Yup.object().shape({
    ip_address: Yup.string()
      .required("IP address is required")
      .test({
        name: "ip-is-valid",
        message: "This is not a valid IP address",
        test: (ip_address) => isIP(formatIpAddress(ip_address, subnet.cidr)),
      })
      .test({
        name: "ip-is-in-subnet",
        message: "The IP address is outside of the subnet's range.",
        test: (ip_address) => {
          const ip = formatIpAddress(ip_address, subnet.cidr);
          if (subnetIsIpv4) {
            return isIpInSubnet(ip, subnet.cidr);
          } else {
            try {
              const addr = ipaddr.parse(ip);
              const netAddr = ipaddr.parse(networkAddress);
              return addr.match(netAddr, prefixLength);
            } catch {
              return false;
            }
          }
        },
      })
      .test({
        name: "ip-already-reserved",
        message: "This IP address is already used or reserved.",
        test: (ip_address) => {
          const ip = formatIpAddress(ip_address, subnet.cidr);
          return (
            !subnetReservedIpList.includes(ip) && !subnetUsedIps.includes(ip)
          );
        },
      }),
    mac_address: Yup.string()
      .required("MAC address is required")
      .matches(MAC_ADDRESS_REGEX, "Invalid MAC address"),
    comment: Yup.string(),
  });

  const handleSubmit = (values: FormValues) => {
    const ip = formatIpAddress(values.ip_address, subnet.cidr);
    dispatch(cleanup());
    if (isEditing) {
      dispatch(
        reservedIpActions.update({
          // IP address cannot be changed, ommitted here
          comment: values.comment,
          mac_address: values.mac_address,
          subnet: subnetId,
          id: reservedIpId,
        })
      );
    } else {
      dispatch(
        reservedIpActions.create({
          comment: values.comment,
          ip,
          mac_address: values.mac_address,
          subnet: subnetId,
        })
      );
    }
  };

  return (
    <FormikForm<FormValues>
      aria-label={
        isEditing ? "Edit static DHCP lease" : "Reserve static DHCP lease"
      }
      cleanup={cleanup}
      enableReinitialize
      errors={errors}
      initialValues={getInitialValues()}
      onCancel={closeSidePanel}
      onSubmit={handleSubmit}
      onSuccess={closeSidePanel}
      resetOnSave
      saved={saved}
      saving={saving}
      submitLabel={
        isEditing ? "Update static DHCP lease" : "Reserve static DHCP lease"
      }
      validationSchema={ReserveDHCPLeaseSchema}
    >
      {({ values }: { values: FormValues }) => (
        <>
          <FormikField
            cidr={subnet.cidr}
            component={PrefixedIpInput}
            disabled={!!reservedIpId}
            help={
              !!reservedIpId ? "You cannot edit a reserved IP address." : null
            }
            label={"IP address"}
            name="ip_address"
            required
          />
          <MacAddressField
            disabled={!!reservedIpId}
            help={
              !!reservedIpId
                ? "You cannot edit a reserved IP's MAC address."
                : null
            }
            label="MAC address"
            name="mac_address"
            required
          />
          <FormikField
            className="u-margin-bottom--x-small"
            label="Comment"
            maxLength={MAX_COMMENT_LENGTH}
            name="comment"
            placeholder="Static DHCP lease purpose"
            type="text"
          />
          <small className="u-flex--end">
            {values.comment.length}/{MAX_COMMENT_LENGTH}
          </small>
        </>
      )}
    </FormikForm>
  );
};

export default ReserveDHCPLease;
