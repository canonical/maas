import * as reduxToolkit from "@reduxjs/toolkit";

import MachineLink, { Labels } from "./MachineLink";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

it("handles when machines are loading", async () => {
  vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("123456");
  const state = factory.rootState({
    machine: factory.machineState({
      items: [
        factory.machine({
          system_id: "abc123",
        }),
      ],
      details: {
        123456: factory.machineStateDetailsItem({
          loading: true,
          system_id: "abc123",
        }),
      },
    }),
  });
  renderWithProviders(<MachineLink systemId="abc123" />, { state });

  expect(screen.getByLabelText(Labels.Loading)).toBeInTheDocument();

  vi.restoreAllMocks();
});

it("handles when a machine does not exist", () => {
  const state = factory.rootState({
    machine: factory.machineState({ items: [], loading: false }),
  });

  renderWithProviders(<MachineLink systemId="abc123" />, {
    state,
  });

  expect(screen.queryByText(/.+/)).not.toBeInTheDocument();
});

it("renders a link if machines have loaded and it exists", () => {
  const machine = factory.machine();
  const state = factory.rootState({
    machine: factory.machineState({ items: [machine], loading: false }),
  });

  renderWithProviders(<MachineLink systemId={machine.system_id} />, { state });

  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    urls.machines.machine.index({ id: machine.system_id })
  );
});
