import type { ReactElement } from "react";

import { ContextualMenu } from "@canonical/react-components";
import { Link, useLocation } from "react-router";

import DeleteSubnet from "../DeleteSubnet";
import EditBootArchitectures from "../EditBootArchitectures";
import MapSubnet from "../MapSubnet";

import SectionHeader from "@/app/base/components/SectionHeader";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { Subnet } from "@/app/store/subnet/types";
import { isSubnetDetails } from "@/app/store/subnet/utils";

type Props = {
  subnet: Subnet | null;
};

const SubnetDetailsHeader = ({ subnet }: Props): ReactElement => {
  const { openSidePanel } = useSidePanel();
  const { pathname } = useLocation();
  const urlBase = `/subnet/${subnet?.id}`;
  return (
    <SectionHeader
      buttons={[
        <ContextualMenu
          hasToggleIcon
          links={[
            {
              children: "Map subnet",
              onClick: () => {
                openSidePanel({
                  component: MapSubnet,
                  title: "Map subnet",
                  props: {
                    subnetId: subnet!.id,
                  },
                });
              },
            },
            {
              children: "Edit boot architectures",
              onClick: () => {
                openSidePanel({
                  component: EditBootArchitectures,
                  title: "Edit boot architectures",
                  props: {
                    subnetId: subnet!.id,
                  },
                  size: "large",
                });
              },
            },
            {
              children: "Delete subnet",
              onClick: () => {
                openSidePanel({
                  component: DeleteSubnet,
                  title: "Delete subnet",
                  props: {
                    subnet: subnet!,
                  },
                });
              },
            },
          ]}
          position="right"
          toggleAppearance="positive"
          toggleLabel="Take action"
        />,
      ]}
      loading={!subnet}
      subtitleLoading={!isSubnetDetails(subnet)}
      tabLinks={[
        {
          active: pathname.startsWith(`${urlBase}/summary`),
          component: Link,
          label: "Subnet summary",
          to: `${urlBase}/summary`,
        },
        {
          active: pathname.startsWith(`${urlBase}/static-routes`),
          component: Link,
          label: "Static routes",
          to: `${urlBase}/static-routes`,
        },
        {
          active: pathname.startsWith(`${urlBase}/address-reservation`),
          component: Link,
          label: "Address reservation",
          to: `${urlBase}/address-reservation`,
        },
        {
          active: pathname.startsWith(`${urlBase}/dhcp-snippets`),
          component: Link,
          label: "DHCP snippets",
          to: `${urlBase}/dhcp-snippets`,
        },
        {
          active: pathname.startsWith(`${urlBase}/used-ip-addresses`),
          component: Link,
          label: "Used IP addresses",
          to: `${urlBase}/used-ip-addresses`,
        },
      ]}
      title={subnet ? subnet.name : ""}
    />
  );
};

export default SubnetDetailsHeader;
