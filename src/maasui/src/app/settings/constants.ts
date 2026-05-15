import type { NavItem } from "@/app/base/components/SecondaryNavigation/SecondaryNavigation";
import settingsURLs from "@/app/settings/urls";

export const settingsNavItems: NavItem[] = [
  {
    label: "Configuration",
    items: [
      { path: settingsURLs.configuration.general, label: "General" },
      {
        path: settingsURLs.configuration.commissioning,
        label: "Commissioning",
      },
      { path: settingsURLs.configuration.deploy, label: "Deploy" },
      {
        path: settingsURLs.configuration.kernelParameters,
        label: "Kernel parameters",
      },
    ],
  },
  {
    label: "Security",
    items: [
      {
        path: settingsURLs.security.securityProtocols,
        label: "Security protocols",
      },
      {
        path: settingsURLs.security.secretStorage,
        label: "Secret storage",
      },
      {
        path: settingsURLs.security.sessionTimeout,
        label: "Token expiration",
      },
      {
        path: settingsURLs.security.ipmiSettings,
        label: "IPMI settings",
      },
    ],
  },
  {
    label: "User management",
    items: [
      {
        path: settingsURLs.userManagement.users,
        label: "Users",
      },
      {
        path: settingsURLs.userManagement.groups,
        label: "Groups",
      },
      {
        label: "OIDC/Single sign-on",
        path: settingsURLs.userManagement.singleSignOn,
      },
    ],
  },
  {
    label: "Images",
    items: [
      { path: settingsURLs.images.ubuntu, label: "Ubuntu" },
      { path: settingsURLs.images.windows, label: "Windows" },
      { path: settingsURLs.images.vmware, label: "VMware" },
      { path: settingsURLs.images.sources, label: "Sources" },
      { path: settingsURLs.images.sync, label: "Synchronization" },
    ],
  },
  {
    path: settingsURLs.licenseKeys.index,
    label: "License keys",
  },
  {
    path: settingsURLs.storage,
    label: "Storage",
  },
  {
    label: "Network",
    items: [
      { path: settingsURLs.network.proxy, label: "Proxy" },
      { path: settingsURLs.network.dns, label: "DNS" },
      { path: settingsURLs.network.ntp, label: "NTP" },
      { path: settingsURLs.network.syslog, label: "Syslog" },
      {
        path: settingsURLs.network.networkDiscovery,
        label: "Network discovery",
      },
    ],
  },
  {
    label: "Scripts",
    items: [
      {
        path: settingsURLs.scripts.commissioning.index,
        label: "Commissioning scripts",
      },
      {
        path: settingsURLs.scripts.deploying.index,
        label: "Deployment scripts",
      },
      {
        path: settingsURLs.scripts.testing.index,
        label: "Testing scripts",
      },
    ],
  },
  {
    path: settingsURLs.dhcp.index,
    label: "DHCP snippets",
  },
  {
    path: settingsURLs.repositories.index,
    label: "Package repos",
  },
];
