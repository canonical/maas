import type { ReactElement } from "react";
import { useState } from "react";

import { ExternalLink, GenericTable } from "@canonical/maas-react-components";
import {
  ContextualMenu,
  Notification as NotificationBanner,
} from "@canonical/react-components";
import classNames from "classnames";
import { useSelector } from "react-redux";

import AddReservedRange from "../AddReservedRange";

import type { ReservedRangesTableData } from "./useReservedRangesTableColumns/useReservedRangesTableColumns";
import useReservedRangesColumns from "./useReservedRangesTableColumns/useReservedRangesTableColumns";

import TitledSection from "@/app/base/components/TitledSection";
import docsUrls from "@/app/base/docsUrls";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { ipRangeActions } from "@/app/store/iprange";
import ipRangeSelectors from "@/app/store/iprange/selectors";
import { IPRangeType } from "@/app/store/iprange/types";
import {
  getCommentDisplay,
  getOwnerDisplay,
  getTypeDisplay,
} from "@/app/store/iprange/utils";
import type { RootState } from "@/app/store/root/types";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import type { VLAN, VLANMeta } from "@/app/store/vlan/types";
import { isId } from "@/app/utils";

export type SubnetProps = {
  subnetId: Subnet[SubnetMeta.PK] | null;
  hasVLANSubnets?: never;
  vlanId?: never;
};

export type VLANProps = {
  hasVLANSubnets?: boolean;
  subnetId?: never;
  vlanId: VLAN[VLANMeta.PK] | null;
};

export type Props = SubnetProps | VLANProps;

export enum Labels {
  Actions = "Actions",
  Comment = "Comment",
  EndIP = "End IP Address",
  Owner = "Owner",
  ReserveDynamicRange = "Reserve dynamic range",
  ReserveRange = "Reserve range",
  StartIP = "Start IP Address",
  Subnet = "Subnet",
  Type = "Type",
}

const ReservedRangesTable = ({
  hasVLANSubnets,
  subnetId,
  vlanId,
}: Props): ReactElement | null => {
  const [isAddingDynamic, setIsAddingDynamic] = useState(false);
  const { openSidePanel } = useSidePanel();
  const isSubnet = isId(subnetId);
  const ipRangeLoading = useSelector(ipRangeSelectors.loading);
  const ipRanges = useSelector((state: RootState) =>
    isSubnet
      ? ipRangeSelectors.getBySubnet(state, subnetId)
      : ipRangeSelectors.getByVLAN(state, vlanId)
  );
  const isDisabled = isId(vlanId) && !hasVLANSubnets;
  const showSubnetColumn = isId(vlanId);

  useFetchActions([ipRangeActions.fetch]);

  const columns = useReservedRangesColumns(showSubnetColumn);

  const data: ReservedRangesTableData[] = ipRanges.map((ipRange) => ({
    id: ipRange.id,
    ipRangeId: ipRange.id,
    subnet: ipRange.subnet,
    startIp: ipRange.start_ip,
    endIp: ipRange.end_ip,
    comment: getCommentDisplay(ipRange),
    type: getTypeDisplay(ipRange),
    owner: getOwnerDisplay(ipRange),
    createType: ipRange.type,
  }));

  return (
    <TitledSection
      buttons={
        <ContextualMenu
          hasToggleIcon
          links={[
            {
              children: Labels.ReserveRange,
              "data-testid": "reserve-range-menu-item",
              onClick: () => {
                openSidePanel({
                  component: AddReservedRange,
                  title: "Reserve range",
                  props: {
                    createType: IPRangeType.Reserved,
                  },
                });
                setIsAddingDynamic(false);
              },
            },
            {
              children: Labels.ReserveDynamicRange,
              "data-testid": "reserve-dynamic-range-menu-item",
              onClick: () => {
                openSidePanel({
                  component: AddReservedRange,
                  title: "Reserve dynamic range",
                  props: {
                    createType: IPRangeType.Dynamic,
                  },
                });
                setIsAddingDynamic(true);
              },
            },
          ]}
          position="right"
          toggleAppearance="positive"
          toggleDisabled={isDisabled}
          toggleLabel={
            isAddingDynamic ? Labels.ReserveDynamicRange : Labels.ReserveRange
          }
        />
      }
      className={classNames({ "u-no-padding--top": isSubnet })}
      title="Reserved ranges"
    >
      {isDisabled ? (
        <NotificationBanner severity="caution">
          No subnets are available on this VLAN. Ranges cannot be reserved.
        </NotificationBanner>
      ) : null}
      <GenericTable
        className={classNames(
          "reserved-ranges-table",
          "p-table-expanding--light",
          {
            "reserved-ranges-table--has-subnet": showSubnetColumn,
          }
        )}
        columns={columns}
        data={data}
        isLoading={ipRangeLoading}
        noData={`No IP ranges have been reserved for this ${isSubnet ? "subnet" : "VLAN"}.`}
        role="table"
        sorting={[{ id: "startIp", desc: false }]}
        variant="regular"
      />
      <ExternalLink to={docsUrls.ipRanges}>About IP ranges</ExternalLink>
    </TitledSection>
  );
};

export default ReservedRangesTable;
