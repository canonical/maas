import type { NavItem } from "@/app/base/components/SecondaryNavigation/SecondaryNavigation";
import urls from "@/app/base/urls";

export const preferencesNavItems: NavItem[] = [
  {
    path: urls.preferences.details,
    label: "Details",
  },
  {
    path: urls.preferences.apiKeys.index,
    label: "API keys",
  },
  {
    path: urls.preferences.sshKeys,
    label: "SSH keys",
  },
  {
    path: urls.preferences.sslKeys,
    label: "SSL keys",
  },
];
