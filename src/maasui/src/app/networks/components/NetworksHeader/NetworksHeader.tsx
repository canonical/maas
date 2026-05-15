import type { ReactElement } from "react";

import { ContextualMenu } from "@canonical/react-components";
import { Link, useLocation } from "react-router";

import AddFabric from "../AddFabric";
import AddSpace from "../AddSpace";
import AddSubnet from "../AddSubnet";
import AddVlan from "../AddVlan";

import SectionHeader from "@/app/base/components/SectionHeader";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";

type Props = {
  controls?: ReactElement;
};

const NetworksHeader = ({ controls }: Props) => {
  const { pathname } = useLocation();
  const { openSidePanel } = useSidePanel();

  return (
    <SectionHeader
      renderButtons={() => (
        <>
          {controls}
          <ContextualMenu
            hasToggleIcon
            links={[
              {
                children: "Fabric",
                onClick: () => {
                  openSidePanel({ component: AddFabric, title: "Add fabric" });
                },
              },
              {
                children: "VLAN",
                onClick: () => {
                  openSidePanel({ component: AddVlan, title: "Add VLAN" });
                },
              },
              {
                children: "Space",
                onClick: () => {
                  openSidePanel({ component: AddSpace, title: "Add space" });
                },
              },
              {
                children: "Subnet",
                onClick: () => {
                  openSidePanel({ component: AddSubnet, title: "Add subnet" });
                },
              },
            ]}
            position="right"
            toggleAppearance="positive"
            toggleLabel="Add"
          />
        </>
      )}
      tabLinks={[
        {
          label: "Subnets",
          to: urls.networks.subnets.index,
          active: pathname.startsWith(urls.networks.subnets.index),
          component: Link,
        },
        {
          label: "VLANs",
          to: urls.networks.vlans.index,
          active: pathname.startsWith(urls.networks.vlans.index),
          component: Link,
        },
        {
          label: "Fabrics",
          to: urls.networks.fabrics.index,
          active: pathname.startsWith(urls.networks.fabrics.index),
          component: Link,
        },
        {
          label: "Spaces",
          to: urls.networks.spaces.index,
          active: pathname.startsWith(urls.networks.spaces.index),
          component: Link,
        },
      ]}
      title="Networks"
    />
  );
};

export default NetworksHeader;
