import type { ReactNode } from "react";
import { Fragment } from "react";

import { Card, Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import NetworkCardTable from "./NetworkCardTable";

import { useFetchActions } from "@/app/base/hooks";
import type { Device } from "@/app/store/device/types";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { NetworkInterface } from "@/app/store/types/node";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";

type InterfaceGroup = {
  firmwareVersion: string;
  interfaces: NetworkInterface[];
  product: string;
  vendor: string;
};

type Props = {
  children?: ReactNode;
  interfaces: NetworkInterface[] | null;
  networkURL: string;
  node: Device | MachineDetails;
};

/**
 * Group physical interfaces by vendor, product and firmware version.
 * @param interfaces - the interfaces to group
 * @returns interfaces grouped by vendor, product and firmware version
 */
const groupInterfaces = (interfaces: NetworkInterface[]): InterfaceGroup[] => {
  const physicalInterfaces = interfaces.filter(
    (iface) => iface.type === "physical"
  );

  // Group interfaces by vendor, product and firmware version
  const interfaceGroups = physicalInterfaces.reduce(
    (groups: InterfaceGroup[], iface: NetworkInterface) => {
      const vendor = iface.vendor || "Unknown network card";
      const product = iface.product || "";
      const firmwareVersion = iface.firmware_version || "";
      const existingGroup = groups.find(
        (group) =>
          group.vendor === vendor &&
          group.product === product &&
          group.firmwareVersion === firmwareVersion
      );

      if (existingGroup) {
        existingGroup.interfaces.push(iface);
      } else {
        groups.push({
          interfaces: [iface],
          vendor,
          product,
          firmwareVersion,
        });
      }
      return groups;
    },
    []
  );

  // Sort groups by vendor, then product, then firmware version. Unknown vendors
  // should appear last.
  return interfaceGroups.sort((a, b) => {
    const vendorA = a.vendor;
    const vendorB = b.vendor;
    const productA = a.product;
    const productB = b.product;
    const versionA = a.firmwareVersion;
    const versionB = b.firmwareVersion;

    if (vendorA === "Unknown network card") {
      return 1;
    }
    if (vendorB === "Unknown network card") {
      return -1;
    }
    if (vendorA === vendorB) {
      if (productA === productB) {
        if (versionA === versionB) {
          return 0;
        }
        return versionA > versionB ? 1 : -1;
      }
      return productA > productB ? 1 : -1;
    }
    return vendorA > vendorB ? 1 : -1;
  });
};

const NodeSummaryNetworkCard = ({
  children,
  interfaces,
  networkURL,
  node,
}: Props): React.ReactElement => {
  const fabricsLoaded = useSelector(fabricSelectors.loaded);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  const subnetsLoaded = useSelector(subnetSelectors.loaded);
  const allNetworkingLoaded = fabricsLoaded && vlansLoaded && subnetsLoaded;

  useFetchActions([
    fabricActions.fetch,
    vlanActions.fetch,
    subnetActions.fetch,
  ]);

  let content: React.ReactElement;

  // Confirm that the full machine details have been fetched. This also allows
  // TypeScript know we're using the right union type (otherwise it will
  // complain that interfaces doesn't exist on the base machine type).
  if (interfaces && allNetworkingLoaded) {
    const groupedInterfaces = groupInterfaces(interfaces);
    content = (
      <>
        {groupedInterfaces.map((group, i) => (
          <Fragment key={i}>
            <ul className="p-inline-list u-no-margin--bottom">
              <li className="p-inline-list__item" data-testid="nic-vendor">
                {group.vendor}
              </li>
              {group.product && (
                <li
                  className="p-inline-list__item u-text--muted"
                  data-testid="nic-product"
                >
                  {group.product}
                </li>
              )}
              {group.firmwareVersion && (
                <li
                  className="p-inline-list__item u-text--muted"
                  data-testid="nic-firmware-version"
                >
                  {group.firmwareVersion}
                </li>
              )}
            </ul>
            <NetworkCardTable interfaces={group.interfaces} node={node} />
          </Fragment>
        ))}
        {children}
      </>
    );
  } else {
    content = <Spinner data-testid="loading-network-data" />;
  }

  return (
    <Card className="network-card">
      <h4 className="p-muted-heading u-sv1">
        <Link to={networkURL}>Network&nbsp;&rsaquo;</Link>
      </h4>
      {content}
    </Card>
  );
};

export default NodeSummaryNetworkCard;
