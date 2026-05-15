import * as fileDownload from "js-file-download";

import DownloadMenu, { Label } from "./DownloadMenu";

import FileContext, { fileContextStore } from "@/app/base/file-context";
import { api } from "@/app/base/sagas/http";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import {
  ScriptResultStatus,
  ScriptResultType,
  ScriptResultNames,
} from "@/app/store/scriptresult/types";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  renderWithProviders,
  waitFor,
} from "@/testing/utils";

vi.mock("js-file-download", () => {
  return {
    default: vi.fn(),
  };
});

describe("DownloadMenu", () => {
  let state: RootState;
  let machine: MachineDetails;
  let controller: ControllerDetails;

  const testDate = new Date(Date.now()).toISOString().split("T")[0];

  beforeEach(() => {
    machine = factory.machineDetails({
      fqdn: "hungry-wombat.aus",
      system_id: "abc123",
    });
    controller = factory.controllerDetails({
      fqdn: "hungry-wombat.aus",
      system_id: "abc123",
    });
    state = factory.rootState({
      controller: factory.controllerState({
        items: [controller],
      }),
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
            status: ScriptResultStatus.PASSED,
          }),
        ],
        logs: {
          1: factory.scriptResultData({
            combined: "installation-output log",
          }),
        },
      }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  afterAll(() => {
    vi.resetAllMocks();
  });

  it("is disabled if there are no downloads", () => {
    state.scriptresult.logs = {};
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    expect(
      screen.getByRole("button", { name: Label.Toggle })
    ).toBeAriaDisabled();
  });

  it("does not display a YAML output item when it does not exist", async () => {
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    expect(
      screen.queryByRole("button", { name: "Machine output (YAML)" })
    ).not.toBeInTheDocument();
  });

  it("can display a YAML output item", async () => {
    vi.spyOn(fileContextStore, "get").mockReturnValue("test yaml file");
    renderWithProviders(
      <FileContext.Provider value={fileContextStore}>
        <DownloadMenu node={machine} />
      </FileContext.Provider>,
      {
        state,
      }
    );
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    expect(
      screen.getByRole("button", { name: "Machine output (YAML)" })
    ).toBeInTheDocument();
  });

  it("generates a download when the installation item is clicked for a machine yml", async () => {
    vi.spyOn(fileContextStore, "get").mockReturnValue("test yaml file");
    const downloadSpy = vi.spyOn(fileDownload, "default");
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    await userEvent.click(
      screen.getByRole("button", { name: "Machine output (YAML)" })
    );
    expect(downloadSpy).toHaveBeenCalledWith(
      "test yaml file",
      `hungry-wombat.aus-machine-output-${testDate}.yaml`
    );
  });

  it("does not display a XML output item when it does not exist", async () => {
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    expect(
      screen.queryByRole("button", { name: "Machine output (XML)" })
    ).not.toBeInTheDocument();
  });

  it("can display a XML output item", async () => {
    vi.spyOn(fileContextStore, "get").mockReturnValue("test xml file");
    renderWithProviders(
      <FileContext.Provider value={fileContextStore}>
        <DownloadMenu node={machine} />
      </FileContext.Provider>,
      {
        state,
      }
    );
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    expect(
      screen.getByRole("button", { name: "Machine output (XML)" })
    ).toBeInTheDocument();
  });

  it("generates a download when the installation item is clicked for a machine xml", async () => {
    vi.spyOn(fileContextStore, "get").mockReturnValue("test xml file");
    const downloadSpy = vi.spyOn(fileDownload, "default");
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    await userEvent.click(
      screen.getByRole("button", { name: "Machine output (XML)" })
    );
    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalledWith(
        "test xml file",
        `hungry-wombat.aus-machine-output-${testDate}.xml`
      );
    });
  });

  it("generates a download when the installation item is clicked for a controller", async () => {
    vi.spyOn(fileContextStore, "get").mockReturnValue("test xml file");
    const downloadSpy = vi.spyOn(fileDownload, "default");
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    await userEvent.click(
      screen.getByRole("button", { name: "Machine output (XML)" })
    );
    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalledWith(
        "test xml file",
        `hungry-wombat.aus-machine-output-${testDate}.xml`
      );
    });
  });

  it("does not display an installation output item when there is no log", async () => {
    state.scriptresult.logs = {};
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    expect(
      screen.queryByRole("button", { name: Label.InstallationOutput })
    ).not.toBeInTheDocument();
  });

  it("can display an installation output item", async () => {
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    expect(
      screen.getByRole("button", { name: Label.InstallationOutput })
    ).toBeInTheDocument();
  });

  it("generates a download when the installation item is clicked", async () => {
    const downloadSpy = vi.spyOn(fileDownload, "default");
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    await userEvent.click(
      screen.getByRole("button", { name: Label.InstallationOutput })
    );
    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalledWith(
        "installation-output log",
        `hungry-wombat.aus-installation-output-${testDate}.log`
      );
    });
  });

  it("does not display curtin logs item when there is no file", async () => {
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    expect(
      screen.queryByRole("button", { name: Label.CurtinLogs })
    ).not.toBeInTheDocument();
  });

  it("can display an curtin logs item for a failed deployment", async () => {
    state.machine.items[0].status = NodeStatus.FAILED_DEPLOYMENT;
    state.nodescriptresult.items.abc123.push(2);
    state.scriptresult.items.push(
      factory.scriptResult({
        id: 2,
        name: ScriptResultNames.CURTIN_LOG,
        result_type: ScriptResultType.INSTALLATION,
        status: ScriptResultStatus.PASSED,
      })
    );
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    expect(
      screen.getByRole("button", { name: Label.CurtinLogs })
    ).toBeInTheDocument();
  });

  it("does not display a curtin logs item for other statuses", async () => {
    state.machine.items[0].status = NodeStatus.FAILED_COMMISSIONING;
    state.nodescriptresult.items.abc123.push(2);
    state.scriptresult.items.push(
      factory.scriptResult({
        id: 2,
        name: ScriptResultNames.CURTIN_LOG,
        result_type: ScriptResultType.INSTALLATION,
        status: ScriptResultStatus.PASSED,
      })
    );
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    expect(
      screen.queryByRole("button", { name: Label.CurtinLogs })
    ).not.toBeInTheDocument();
  });

  it("generates a download when the curtin logs item is clicked", async () => {
    state.machine.items[0].status = NodeStatus.FAILED_DEPLOYMENT;
    state.nodescriptresult.items.abc123.push(2);
    state.scriptresult.items.push(
      factory.scriptResult({
        id: 2,
        name: ScriptResultNames.CURTIN_LOG,
        result_type: ScriptResultType.INSTALLATION,
        status: ScriptResultStatus.PASSED,
      })
    );
    vi.spyOn(api.scriptresults, "getCurtinLogsTar").mockResolvedValue(
      "curtin-logs-blob"
    );
    const downloadSpy = vi.spyOn(fileDownload, "default");
    renderWithProviders(<DownloadMenu node={machine} />, {
      state,
    });
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: Label.Toggle }));
    await userEvent.click(
      screen.getByRole("button", { name: Label.CurtinLogs })
    );
    await Promise.resolve();
    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalledWith(
        "curtin-logs-blob",
        `hungry-wombat.aus-curtin-${testDate}.tar`
      );
    });
  });
});
