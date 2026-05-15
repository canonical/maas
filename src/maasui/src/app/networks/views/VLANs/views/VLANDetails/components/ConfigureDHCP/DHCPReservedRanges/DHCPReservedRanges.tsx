import { useEffect } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { ConfigureDHCPValues } from "../ConfigureDHCP";

import type { DHCPReservedRangeData } from "./useDHCPReservedRangesColumns";
import useDHCPReservedRangesColumns from "./useDHCPReservedRangesColumns";

import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import TitledSection from "@/app/base/components/TitledSection";
import { useFetchActions } from "@/app/base/hooks";
import { ipRangeActions } from "@/app/store/iprange";
import ipRangeSelectors from "@/app/store/iprange/selectors";
import { getCommentDisplay } from "@/app/store/iprange/utils";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";
import { isId } from "@/app/utils";

type Props = {
  id: VLAN[VLANMeta.PK];
};

export enum Headers {
  Comment = "Comment",
  EndIP = "End IP address",
  GatewayIP = "Gateway IP",
  StartIP = "Start IP address",
  Subnet = "Subnet",
}

const DHCPReservedRanges = ({ id }: Props): React.ReactElement | null => {
  const { setFieldTouched, setFieldValue, validateForm, values } =
    useFormikContext<ConfigureDHCPValues>();

  const ipRanges = useSelector((state: RootState) =>
    ipRangeSelectors.getByVLAN(state, id)
  );
  const subnets = useSelector(subnetSelectors.all);
  const ipRangeLoading = useSelector(ipRangeSelectors.loading);

  useFetchActions([ipRangeActions.fetch, subnetActions.fetch]);

  const hasIPRanges = ipRanges.length > 0;
  const subnetSelected = isId(values.subnet);

  // When the selected subnet changes, populate the reserved range defaults
  // based on the subnet's suggested dynamic range, or clear the fields.
  useEffect(() => {
    const subnet = subnets.find((s) => s.id === Number(values.subnet));
    setFieldValue(
      "endIP",
      subnet?.statistics.suggested_dynamic_range?.end || ""
    ).catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "endIP",
        "setFieldValue",
        reason as string
      );
    });
    setFieldValue(
      "gatewayIP",
      subnet?.gateway_ip || subnet?.statistics.suggested_gateway || ""
    ).catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "gatewayIP",
        "setFieldValue",
        reason as string
      );
    });
    setFieldValue(
      "startIP",
      subnet?.statistics.suggested_dynamic_range?.start || ""
    ).catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "startIP",
        "setFieldValue",
        reason as string
      );
    });
    if (isId(values.subnet)) {
      setFieldTouched("subnet", true, false);
    }
    // need to manually call this as Yup does not automatically re-trigger the validation schema
    validateForm();
  }, [setFieldTouched, setFieldValue, subnets, validateForm, values.subnet]);

  const columns = useDHCPReservedRangesColumns({
    hasIPRanges,
    subnetSelected,
    vlanId: id,
  });

  if (!values.enableDHCP) {
    return null;
  }

  const data: DHCPReservedRangeData[] = hasIPRanges
    ? ipRanges.map((ipRange) => {
        const subnet = subnets.find((subnet) => subnet.id === ipRange.subnet);
        return {
          id: ipRange.id,
          subnet: ipRange.subnet,
          startIp: ipRange.start_ip,
          endIp: ipRange.end_ip,
          gatewayIp: subnet?.gateway_ip || "—",
          comment: getCommentDisplay(ipRange),
        };
      })
    : [
        {
          id: 0,
          subnet: values.subnet || 0,
          startIp: values.startIP,
          endIp: values.endIP,
          gatewayIp: values.gatewayIP,
          comment: "",
        },
      ];

  return (
    <TitledSection title="Reserved dynamic range">
      <GenericTable
        columns={columns}
        data={data}
        isLoading={hasIPRanges ? ipRangeLoading : false}
        noData={hasIPRanges ? "No IP ranges have been reserved." : ""}
        sorting={hasIPRanges ? [{ id: "startIp", desc: false }] : undefined}
        variant="regular"
      />
    </TitledSection>
  );
};

export default DHCPReservedRanges;
