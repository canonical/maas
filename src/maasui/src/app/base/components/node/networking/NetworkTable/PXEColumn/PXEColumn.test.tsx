import PXEColumn from "./PXEColumn";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

describe("PXEColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
        loaded: true,
        statuses: {
          abc123: factory.machineStatus(),
        },
      }),
    });
  });

  it("can display a boot icon", () => {
    const nic = factory.machineInterface({
      is_boot: true,
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    renderWithProviders(<PXEColumn nic={nic} node={machine} />, { state });

    expect(document.querySelector(".p-icon--tick")).toBeInTheDocument();
  });

  it("does not display an icon if it is not a boot interface", () => {
    const nic = factory.machineInterface({
      is_boot: false,
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    renderWithProviders(<PXEColumn nic={nic} node={machine} />, { state });

    expect(document.querySelector(".p-icon--tick")).not.toBeInTheDocument();
  });
});
