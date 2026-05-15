import { useMemo } from "react";

import { Button, Icon } from "@canonical/react-components";
import type { ColumnDef, Row } from "@tanstack/react-table";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import DoubleRow from "@/app/base/components/DoubleRow";
import MacAddressDisplay from "@/app/base/components/MacAddressDisplay";
import urls from "@/app/base/urls";
import type { DeviceRow } from "@/app/devices/components/DevicesTable/DevicesTable";
import { getIpAssignmentDisplay } from "@/app/store/device/utils";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag } from "@/app/store/tag/types";
import { getTagsDisplay } from "@/app/store/tag/utils";

type DeviceColumnDef = ColumnDef<DeviceRow, Partial<DeviceRow>>;

const getDeviceTags = (device: DeviceRow, tags: Tag[]): Tag[] => {
  return tags.filter((tag) => device.tags.includes(tag.id));
};

const useDevicesTableColumns = (): DeviceColumnDef[] => {
  const tags = useSelector((state: RootState) => tagSelectors.all(state));

  return useMemo(
    () => [
      {
        id: "fqdn",
        accessorKey: "fqdn",
        enableSorting: true,
        meta: { isInteractiveHeader: true },
        header: (header) => (
          <>
            <Button
              appearance="link"
              className="p-button--column-header"
              data-testid="fqdn-header"
              onClick={(e) => {
                e.stopPropagation();
                const sortingFn = header.column.getToggleSortingHandler();
                sortingFn && sortingFn(e);
              }}
              type="button"
            >
              FQDN
            </Button>
            {{
              asc: <Icon name={"chevron-up"}>ascending</Icon>,
              desc: <Icon name={"chevron-down"}>descending</Icon>,
            }[header?.column?.getIsSorted() as string] ?? null}
            <br />
            <span>MAC address</span>
          </>
        ),
        cell: ({
          row: {
            original: {
              fqdn,
              system_id,
              hostname,
              domain,
              primary_mac,
              extra_macs,
            },
          },
        }: {
          row: Row<DeviceRow>;
        }) => {
          const macDisplay = extra_macs.length
            ? `${primary_mac} (+${extra_macs.length})`
            : primary_mac;

          return (
            <DoubleRow
              primary={
                <Link to={urls.devices.device.index({ id: system_id })}>
                  <strong>{hostname}</strong>
                  <span>.{domain.name}</span>
                </Link>
              }
              primaryTitle={fqdn}
              secondary={<MacAddressDisplay>{macDisplay}</MacAddressDisplay>}
              secondaryTitle={[primary_mac, ...extra_macs].join(", ")}
            />
          );
        },
      },
      {
        id: "ip_assignment",
        accessorKey: "ip_assignment",
        enableSorting: true,
        meta: { isInteractiveHeader: true },
        header: (header) => (
          <>
            <Button
              appearance="link"
              className="p-button--column-header"
              data-testid="ip-header"
              onClick={(e) => {
                e.stopPropagation();
                const sortingFn = header.column.getToggleSortingHandler();
                sortingFn && sortingFn(e);
              }}
              type="button"
            >
              IP assignment
            </Button>
            {{
              asc: <Icon name={"chevron-up"}>ascending</Icon>,
              desc: <Icon name={"chevron-down"}>descending</Icon>,
            }[header?.column?.getIsSorted() as string] ?? null}
            <br />
            <span>IP address</span>
          </>
        ),
        cell: ({
          row: {
            original: { ip_assignment, ip_address },
          },
        }: {
          row: Row<DeviceRow>;
        }) => {
          const ipAssignment = getIpAssignmentDisplay(ip_assignment);

          return (
            <DoubleRow
              primary={ipAssignment}
              primaryTitle={ipAssignment}
              secondary={ip_address}
              secondaryTitle={ip_address}
            />
          );
        },
      },
      {
        id: "zone",
        accessorKey: "zone",
        enableSorting: true,
        header: "Zone",
        cell: ({
          row: {
            original: { zone },
          },
        }: {
          row: Row<DeviceRow>;
        }) => (
          <Link className="p-link--soft" to={urls.zones.index}>
            {zone}
          </Link>
        ),
      },
      {
        id: "owner",
        accessorKey: "owner",
        enableSorting: true,
        meta: { isInteractiveHeader: true },
        header: (header) => (
          <>
            <Button
              appearance="link"
              className="p-button--column-header"
              data-testid="owner-header"
              onClick={(e) => {
                e.stopPropagation();
                const sortingFn = header.column.getToggleSortingHandler();
                sortingFn && sortingFn(e);
              }}
              type="button"
            >
              Owner
            </Button>
            {{
              asc: <Icon name={"chevron-up"}>ascending</Icon>,
              desc: <Icon name={"chevron-down"}>descending</Icon>,
            }[header?.column?.getIsSorted() as string] ?? null}
            <br />
            <span>Tags</span>
          </>
        ),
        cell: ({ row: { original: device } }: { row: Row<DeviceRow> }) => {
          const tagDisplay = getTagsDisplay(getDeviceTags(device, tags));

          return (
            <DoubleRow
              primary={device.owner}
              primaryTitle={device.owner}
              secondary={tagDisplay}
              secondaryTitle={tagDisplay}
            />
          );
        },
      },
    ],
    [tags]
  );
};

export default useDevicesTableColumns;
