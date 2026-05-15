import { define, random } from "cooky-cutter";

import type { SshKeyResponse } from "@/app/apiclient";

export const sshKey = define<SshKeyResponse>({
  id: random,
  key: "test key",
  protocol: "gh",
  auth_id: "test auth id",
  kind: "sshkey",
});
