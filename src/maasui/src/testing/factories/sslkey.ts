import { define, random } from "cooky-cutter";

import type { SslKeyResponse } from "@/app/apiclient";

export const sslKey = define<SslKeyResponse>({
  id: random,
  key: (i: number) => `test key ${i}`,
  kind: "",
});
