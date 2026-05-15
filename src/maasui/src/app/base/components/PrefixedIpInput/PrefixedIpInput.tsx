import type { ClipboardEvent, ReactElement } from "react";

import { useFormikContext } from "formik";
import { isIPv4 } from "is-ip";

import PrefixedInput from "../PrefixedInput";
import type { PrefixedInputProps } from "../PrefixedInput/PrefixedInput";

import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import type { Subnet } from "@/app/store/subnet/types";
import {
  getImmutableAndEditableOctets,
  getIpRangeFromCidr,
} from "@/app/utils/subnetIpRange";

type Props = Omit<
  PrefixedInputProps,
  "immutableText" | "maxLength" | "name" | "placeholder"
> & {
  cidr: Subnet["cidr"];
  name: string;
};

const PrefixedIpInput = ({
  cidr,
  name,
  help,
  ...props
}: Props): ReactElement => {
  const [networkAddress] = cidr.split("/");
  const ipv6Prefix = networkAddress.substring(
    0,
    networkAddress.lastIndexOf(":")
  );
  const subnetIsIpv4 = isIPv4(networkAddress);

  const [startIp, endIp] = getIpRangeFromCidr(cidr);
  const [immutable, editable] = getImmutableAndEditableOctets(startIp, endIp);

  const formikProps = useFormikContext();

  const getIPv6Placeholder = () => {
    // 7 is the maximum number of colons in an IPv6 address
    const placeholderColons = 7 - (ipv6Prefix.match(/:/g) || []).length;
    return `${"0000:".repeat(placeholderColons)}0000`;
  };

  const getPlaceholderText = () =>
    subnetIsIpv4 ? editable : getIPv6Placeholder();

  const getIPv4MaxLength = () => {
    const immutableOctetsLength = immutable.split(".").length;
    const lengths = [15, 11, 7, 3]; // Corresponding to 0-3 immutable octets
    return lengths[immutableOctetsLength];
  };

  const getMaxLength = () =>
    subnetIsIpv4 ? getIPv4MaxLength() : getIPv6Placeholder().length;

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pastedText = e.clipboardData.getData("text");
    if (subnetIsIpv4) {
      const octets = pastedText.split(".");
      const trimmed = octets.slice(0 - editable.split(".").length);
      formikProps
        .setFieldValue(name, trimmed.join("."))
        .catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            name,
            "setFieldValue",
            reason as string
          );
        });
    } else {
      const interfaceId = pastedText.replace(ipv6Prefix, "");
      formikProps.setFieldValue(name, interfaceId).catch((reason: unknown) => {
        throw new FormikFieldChangeError(
          name,
          "setFieldValue",
          reason as string
        );
      });
    }
  };

  return (
    <PrefixedInput
      help={
        help ? (
          help
        ) : subnetIsIpv4 ? (
          <>
            The available range in this subnet is{" "}
            <code>
              {immutable}.{editable}
            </code>
          </>
        ) : null
      }
      immutableText={subnetIsIpv4 ? `${immutable}.` : ipv6Prefix}
      maxLength={getMaxLength()}
      name={name}
      onPaste={handlePaste}
      placeholder={getPlaceholderText()}
      {...props}
    />
  );
};

export default PrefixedIpInput;
