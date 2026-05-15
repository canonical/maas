import InstallationOutput, { Label } from "./InstallationOutput";

import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import type { ScriptResult } from "@/app/store/scriptresult/types";
import {
  ScriptResultNames,
  ScriptResultStatus,
  ScriptResultType,
} from "@/app/store/scriptresult/types";
import { PowerState } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("InstallationOutput", () => {
  let state: RootState;
  let machine: MachineDetails;

  beforeEach(() => {
    machine = factory.machineDetails({ system_id: "abc123" });
    state = factory.rootState({
      machine: factory.machineState({
        items: [machine],
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1] },
      }),
      scriptresult: factory.scriptResultState({
        items: [
          factory.scriptResult({
            id: 1,
            name: ScriptResultNames.INSTALL_LOG,
            result_type: ScriptResultType.INSTALLATION,
          }),
        ],
        logs: {
          1: factory.scriptResultData({
            combined: "script result",
          }),
        },
      }),
    });
  });

  it("displays a spinner when the logs are loading", () => {
    state.scriptresult.loading = true;
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByLabelText(Label.Loading)).toBeInTheDocument();
  });

  it("displays the state when there is no result", () => {
    state.scriptresult.items = [];
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText(Label.None)).toBeInTheDocument();
  });

  it("displays the state when the machine is off", () => {
    state.scriptresult.items[0].status = ScriptResultStatus.PENDING;
    state.machine.items[0].power_state = PowerState.OFF;
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText(Label.Off)).toBeInTheDocument();
  });

  it("displays the state when the machine is booting", () => {
    state.scriptresult.items[0].status = ScriptResultStatus.PENDING;
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText(Label.Booting)).toBeInTheDocument();
  });

  it("displays the state when the machine is installing", () => {
    state.scriptresult.items[0].status = ScriptResultStatus.RUNNING;
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText(Label.Begun)).toBeInTheDocument();
  });

  it("displays the state when the machine has installed but no result", () => {
    state.scriptresult.items[0].status = ScriptResultStatus.PASSED;
    state.scriptresult.logs = {
      1: factory.scriptResultData({
        combined: undefined,
      }),
    };
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText(Label.SucceededNoOutput)).toBeInTheDocument();
  });

  it("can display the installation log", () => {
    state.scriptresult.items[0].status = ScriptResultStatus.PASSED;
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText("script result")).toBeInTheDocument();
  });

  it("displays the state when the installation failed without result", () => {
    state.scriptresult.items[0].status = ScriptResultStatus.FAILED;
    state.scriptresult.logs = {
      1: factory.scriptResultData({
        combined: undefined,
      }),
    };
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText(Label.FailedNoOutput)).toBeInTheDocument();
  });

  it("displays the log when the installation failed", () => {
    state.scriptresult.items[0].status = ScriptResultStatus.FAILED;
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText("script result")).toBeInTheDocument();
  });

  it("displays the state when the installation timed out", () => {
    state.scriptresult.items[0].status = ScriptResultStatus.TIMEDOUT;
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText(Label.Timeout)).toBeInTheDocument();
  });

  it("displays the state when the installation was aborted", () => {
    state.scriptresult.items[0].status = ScriptResultStatus.ABORTED;
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText(Label.Aborted)).toBeInTheDocument();
  });

  it("displays the state the installation status is unknown", () => {
    state.scriptresult.items = [
      factory.scriptResult({
        id: 1,
        name: ScriptResultNames.INSTALL_LOG,
        result_type: ScriptResultType.INSTALLATION,
        status: "huh???",
      } as Partial<ScriptResult> & { status: string }),
    ];
    renderWithProviders(<InstallationOutput node={machine} />, {
      state,
    });
    expect(screen.getByText("Unknown log status huh???")).toBeInTheDocument();
  });
});
