import { Factory } from "fishery";

import type { BootSourceResponse } from "@/app/apiclient";

export const imageSourceFactory = Factory.define<BootSourceResponse>(
  ({ sequence }) => ({
    id: sequence,
    name: "MAAS Stable",
    url: "http://images.maas.io/ephemeral-v3/stable/",
    keyring_filename: "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg",
    keyring_data: "aabbccdd",
    priority: sequence,
    skip_keyring_verification: false,
    enabled: true,
  })
);
