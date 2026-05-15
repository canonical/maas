import { isEphemerallyDeployed } from "./IsEphemerallyDeployed";

import { NodeStatusCode } from "@/app/store/types/node";
import * as factory from "@/testing/factories";

it("returns true if a machine is deployed ephemerally", () => {
  const machine = factory.machine({
    system_id: "abc123",
    status_code: NodeStatusCode.DEPLOYED,
    ephemeral_deploy: true,
  });

  expect(isEphemerallyDeployed(machine)).toBe(true);
});

it("returns false if a machine is not deployed ephemerally", () => {
  const machine = factory.machine({
    system_id: "abc123",
    status_code: NodeStatusCode.DEPLOYED,
    ephemeral_deploy: false,
  });

  expect(isEphemerallyDeployed(machine)).toBe(false);
});
