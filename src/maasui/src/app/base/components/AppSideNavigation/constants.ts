import type { NavGroup } from "./types";

import urls from "@/app/base/urls";

const navGroups: NavGroup[] = [
  {
    groupTitle: "Hardware",
    groupIcon: "machines",
    navLinks: [
      {
        highlight: [urls.machines.index, urls.machines.machine.index(null)],
        label: "Machines",
        url: urls.machines.index,
      },
      ...(import.meta.env.VITE_APP_SWITCH_PROVISIONING === "true"
        ? [
            {
              highlight: [urls.switches.index],
              label: "Switches",
              url: urls.switches.index,
            },
          ]
        : []),
      {
        highlight: [urls.devices.index, urls.devices.device.index(null)],
        label: "Devices",
        url: urls.devices.index,
      },
      {
        adminOnly: true,
        highlight: [
          urls.controllers.index,
          urls.controllers.controller.index(null),
        ],
        label: "Controllers",
        url: urls.controllers.index,
      },
      ...(import.meta.env.VITE_APP_AGENT_ENROLLMENT === "true"
        ? [
            {
              highlight: [urls.racks.index],
              label: "Racks",
              url: urls.racks.index,
            },
          ]
        : []),
    ],
  },
  {
    groupTitle: "KVM",
    groupIcon: "cluster-light",
    navLinks: [
      {
        label: "LXD",
        url: urls.kvm.lxd.index,
      },
      {
        label: "Virsh",
        url: urls.kvm.virsh.index,
      },
    ],
  },
  {
    groupTitle: "Organisation",
    groupIcon: "tag",
    navLinks: [
      {
        highlight: [urls.tags.index, urls.tags.tag.index(null)],
        label: "Tags",
        url: urls.tags.index,
      },
      {
        highlight: [urls.zones.index],
        label: "AZs",
        url: urls.zones.index,
      },
      {
        label: "Pools",
        url: urls.pools.index,
      },
    ],
  },
  {
    groupTitle: "Configuration",
    groupIcon: "units",
    navLinks: [
      {
        label: "Images",
        url: urls.images.index,
      },
    ],
  },
  {
    groupTitle: "Networking",
    groupIcon: "connected",
    navLinks: [
      {
        highlight: [
          urls.networks.index,
          urls.networks.subnets.index,
          urls.networks.fabrics.index,
          urls.networks.spaces.index,
          urls.networks.vlans.index,
          urls.networks.subnet.index(null),
          urls.networks.space.index(null),
          urls.networks.fabric.index(null),
          urls.networks.vlan.index(null),
        ],
        label: "Networks",
        url: urls.networks.subnets.indexWithParams({ by: "fabric" }),
      },
      {
        highlight: [urls.domains.index, urls.domains.details(null)],
        label: "DNS",
        url: urls.domains.index,
      },
      {
        label: "Network discovery",
        url: urls.networkDiscovery.index,
      },
    ],
  },
];

export { navGroups };
