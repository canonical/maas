import * as reactComponentHooks from "@canonical/react-components/dist/hooks";
import { screen } from "@testing-library/react";

import MachineCommissioning from ".";

import { HardwareType } from "@/app/base/enum";
import type { RootState } from "@/app/store/root/types";
import { ScriptResultType } from "@/app/store/scriptresult/types";
import { TestStatusStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

vi.mock("@canonical/react-components/dist/hooks", () => {
  const hooks = vi.importActual("@canonical/react-components/dist/hooks");
  return {
    ...hooks,
    usePrevious: vi.fn(),
  };
});

describe("MachineCommissioning", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machineDetails({
            locked: false,
            permissions: ["edit"],
            system_id: "abc123",
          }),
        ],
      }),
      scriptresult: factory.scriptResultState({
        loaded: true,
      }),
    });
  });

  it("renders the spinner while script results are loading.", () => {
    renderWithProviders(<MachineCommissioning />, {
      state,
      initialEntries: ["/machine/abc123"],
      pattern: "/machine/:id",
    });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("fetches script results if they haven't been fetched", () => {
    state.nodescriptresult.items = { abc123: [] };
    state.scriptresult.items = [];

    const { store } = renderWithProviders(<MachineCommissioning />, {
      state,
      initialEntries: ["/machine/abc123"],
      pattern: "/machine/:id",
    });
    expect(
      store
        .getActions()
        .some((action) => action.type === "scriptresult/getByNodeId")
    ).toBe(true);
  });

  it("does not fetch script results if they have already been loaded", () => {
    state.nodescriptresult.items = { abc123: [] };
    state.scriptresult.items = [];

    const { store, rerender } = renderWithProviders(<MachineCommissioning />, {
      state,
      initialEntries: ["/machine/abc123"],
      pattern: "/machine/:id",
    });
    expect(
      store
        .getActions()
        .filter((action) => action.type === "scriptresult/getByNodeId").length
    ).toBe(1);
    rerender(<MachineCommissioning />, {
      state,
    });
    expect(
      store
        .getActions()
        .filter((action) => action.type === "scriptresult/getByNodeId").length
    ).toBe(1);
  });

  it("refetchs script results when the machine commissioning status changes", () => {
    vi.spyOn(reactComponentHooks, "usePrevious").mockImplementation(
      () => TestStatusStatus.PASSED
    );
    state.machine.items = [
      factory.machineDetails({
        commissioning_status: factory.testStatus({
          status: TestStatusStatus.PENDING,
        }),
        locked: false,
        permissions: ["edit"],
        system_id: "abc123",
      }),
    ];
    state.nodescriptresult.items = { abc123: [1] };
    state.scriptresult.items = [
      factory.scriptResult({
        id: 1,
        result_type: ScriptResultType.TESTING,
        hardware_type: HardwareType.CPU,
      }),
    ];

    const { store } = renderWithProviders(<MachineCommissioning />, {
      state,
      initialEntries: ["/machine/abc123"],
      pattern: "/machine/:id",
    });
    expect(
      store
        .getActions()
        .filter((action) => action.type === "scriptresult/getByNodeId").length
    ).toBe(1);
  });
});
