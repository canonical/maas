import { getStatusText } from "./getStatusText";

import { NodeStatus, NodeStatusCode } from "@/app/store/types/node";
import * as factory from "@/testing/factories";

describe("getStatusText", () => {
  it("displays the machine's status if not deploying or deployed", () => {
    const machine = factory.machine({
      status: NodeStatus.NEW,
      status_code: NodeStatusCode.NEW,
    });
    expect(getStatusText(machine, "Ubuntu 18.04 LTS")).toEqual("New");
  });

  it("displays the release name if machine is deployed", () => {
    const machine = factory.machine({ status_code: NodeStatusCode.DEPLOYED });

    expect(getStatusText(machine, "Ubuntu 18.04 LTS")).toEqual(
      "Ubuntu 18.04 LTS"
    );
  });

  it("displays 'Deploying OS release' if machine is deploying", () => {
    const machine = factory.machine({ status_code: NodeStatusCode.DEPLOYING });

    expect(getStatusText(machine, "Ubuntu 18.04 LTS")).toEqual(
      "Deploying Ubuntu 18.04 LTS"
    );
  });
});
