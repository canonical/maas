import type { Accept } from "react-dropzone";

export const MAAS_IO_URLS = {
  stable: "http://images.maas.io/ephemeral-v3/stable",
  candidate: "http://images.maas.io/ephemeral-v3/candidate",
} as const;

export const MAAS_IO_DEFAULT_KEYRING_FILE_PATHS = {
  deb: "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg",
  snap: "/snap/maas/current/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg",
};

export const MAAS_IO_DEFAULTS = {
  url: MAAS_IO_URLS.stable,
  keyring_filename:
    "/snap/maas/current/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg",
  keyring_data: "",
} as const;

export const VALID_IMAGE_FILE_TYPES: Accept = {
  "application/octet-stream": [
    ".tgz",
    ".tbz",
    ".txz",
    ".ddtgz",
    ".ddtbz",
    ".ddtxz",
    ".ddtar",
    ".ddbz2",
    ".ddgz",
    ".ddxz",
    ".ddraw",
  ],
} as const;

export const OPERATING_SYSTEM_NAMES = [
  {
    label: "Ubuntu Core",
    value: "Ubuntu Core",
  },
  {
    label: "CentOS",
    value: "CentOS",
  },
  {
    label: "RHEL",
    value: "RHEL",
  },
  {
    label: "Windows",
    value: "Windows",
  },
  {
    label: "SUSE",
    value: "SUSE",
  },
  {
    label: "ESXi",
    value: "ESXi",
  },
  {
    label: "Oracle Linux",
    value: "OL",
  },
  {
    label: "Custom",
    value: "Custom",
  },
] as const;

export const BASE_IMAGE_OPERATING_SYSTEM_NAMES = [
  {
    label: "Ubuntu",
    value: "Ubuntu",
  },
  {
    label: "CentOS",
    value: "CentOS",
  },
  {
    label: "RHEL",
    value: "RHEL",
  },
  {
    label: "Oracle Linux",
    value: "OL",
  },
] as const;

// TODO: Finalise valid architecture options https://warthogs.atlassian.net/browse/MAASENG-2716
export const ARCHITECTURES = [
  {
    label: "amd64",
    value: "amd64",
  },
  {
    label: "armhf",
    value: "armhf",
  },
  {
    label: "arm64",
    value: "arm64",
  },
  {
    label: "i386",
    value: "i386",
  },
] as const;
