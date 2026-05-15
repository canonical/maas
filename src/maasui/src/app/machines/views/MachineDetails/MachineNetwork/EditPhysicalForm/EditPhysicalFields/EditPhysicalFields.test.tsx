import { Formik } from "formik";

import EditPhysicalFields from "./EditPhysicalFields";

import type { RootState } from "@/app/store/root/types";
import type { NetworkInterface } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("EditPhysicalFields", () => {
  let nic: NetworkInterface;
  let state: RootState;

  beforeEach(() => {
    nic = factory.machineInterface({
      id: 1,
    });
    state = factory.rootState({
      fabric: factory.fabricState({
        items: [factory.fabric({}), factory.fabric()],
        loaded: true,
      }),
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            interfaces: [nic],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
      subnet: factory.subnetState({
        items: [factory.subnet(), factory.subnet()],
        loaded: true,
      }),
      vlan: factory.vlanState({
        items: [factory.vlan(), factory.vlan()],
        loaded: true,
      }),
    });
  });

  it("shows a warning if link speed is higher than interface speed", async () => {
    renderWithProviders(
      <Formik
        initialValues={{ interface_speed: 0, link_speed: 0 }}
        onSubmit={vi.fn()}
      >
        <EditPhysicalFields nic={nic} />
      </Formik>,
      {
        state,
      }
    );

    const interfaceSpeedInput = screen.getByRole("textbox", {
      name: "Interface speed (Gbps)",
    });
    const linkSpeedInput = screen.getByRole("textbox", {
      name: "Link speed (Gbps)",
    });

    await userEvent.type(interfaceSpeedInput, "1");
    await userEvent.type(linkSpeedInput, "2");

    await userEvent.tab();

    expect(
      screen.getByText(/Link speed should not be higher than interface speed/i)
    ).toBeInTheDocument();
  });
});
