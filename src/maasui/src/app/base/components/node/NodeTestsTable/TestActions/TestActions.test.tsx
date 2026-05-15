import type { Mock, SpyInstance } from "vitest";

import TestActions from "./TestActions";

import * as hooks from "@/app/base/hooks/analytics";
import urls from "@/app/base/urls";
import {
  ScriptResultStatus,
  ScriptResultType,
} from "@/app/store/scriptresult/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

const openMenu = async () => {
  await userEvent.click(screen.getByRole("button", { name: "Take action:" }));
};

describe("TestActions", () => {
  let mockSendAnalytics: Mock;
  let mockUseSendAnalytics: SpyInstance;

  beforeEach(() => {
    mockSendAnalytics = vi.fn();
    mockUseSendAnalytics = vi
      .spyOn(hooks, "useSendAnalytics")
      .mockImplementation(() => mockSendAnalytics);
  });

  afterEach(() => {
    mockSendAnalytics.mockRestore();
    mockUseSendAnalytics.mockRestore();
  });

  it("can display an action to view machine commissioning script details", async () => {
    const machine = factory.machineDetails();
    const scriptResult = factory.scriptResult({
      status: ScriptResultStatus.PASSED,
    });
    renderWithProviders(
      <TestActions
        node={machine}
        resultType={ScriptResultType.COMMISSIONING}
        scriptResult={scriptResult}
        setExpanded={vi.fn()}
      />
    );

    await openMenu();

    expect(screen.getByRole("link", { name: /View details/i })).toHaveAttribute(
      "href",
      urls.machines.machine.commissioning.scriptResult({
        id: machine.system_id,
        scriptResultId: scriptResult.id,
      })
    );
  });

  it("can display an action to view controller commissioning script details", async () => {
    const controller = factory.controllerDetails();
    const scriptResult = factory.scriptResult({
      status: ScriptResultStatus.PASSED,
    });
    renderWithProviders(
      <TestActions
        node={controller}
        resultType={ScriptResultType.COMMISSIONING}
        scriptResult={scriptResult}
        setExpanded={vi.fn()}
      />
    );

    await openMenu();
    expect(screen.getByRole("link", { name: /View details/i })).toHaveAttribute(
      "href",
      urls.controllers.controller.commissioning.scriptResult({
        id: controller.system_id,
        scriptResultId: scriptResult.id,
      })
    );
  });

  it("can display an action to view machine testing script details", async () => {
    const machine = factory.machineDetails();
    const scriptResult = factory.scriptResult({
      status: ScriptResultStatus.PASSED,
    });
    renderWithProviders(
      <TestActions
        node={machine}
        resultType={ScriptResultType.TESTING}
        scriptResult={scriptResult}
        setExpanded={vi.fn()}
      />
    );

    await openMenu();

    expect(screen.getByRole("link", { name: /View details/i })).toHaveAttribute(
      "href",
      urls.machines.machine.testing.scriptResult({
        id: machine.system_id,
        scriptResultId: scriptResult.id,
      })
    );
  });

  it("displays an action to view metrics if the test has its own results", async () => {
    const machine = factory.machineDetails();
    const scriptResult = factory.scriptResult({
      results: [factory.scriptResultResult()],
    });
    renderWithProviders(
      <TestActions
        node={machine}
        resultType={ScriptResultType.TESTING}
        scriptResult={scriptResult}
        setExpanded={vi.fn()}
      />
    );

    await openMenu();
    expect(
      screen.getByRole("button", { name: /View metrics/i })
    ).toBeInTheDocument();
  });

  it("sends an analytics event when clicking the 'View previous tests' button", async () => {
    const machine = factory.machineDetails();
    const scriptResult = factory.scriptResult();
    renderWithProviders(
      <TestActions
        node={machine}
        resultType={ScriptResultType.TESTING}
        scriptResult={scriptResult}
        setExpanded={vi.fn()}
      />
    );

    await openMenu();
    await userEvent.click(
      screen.getByRole("button", { name: /view previous tests/i })
    );

    expect(mockSendAnalytics).toHaveBeenCalled();
    expect(mockSendAnalytics.mock.calls[0]).toEqual([
      "Machine testing",
      "View testing script history",
      "View previous tests",
    ]);
  });

  it("sends an analytics event when clicking the 'View metrics' button", async () => {
    const machine = factory.machineDetails();
    const scriptResult = factory.scriptResult();
    renderWithProviders(
      <TestActions
        node={machine}
        resultType={ScriptResultType.TESTING}
        scriptResult={scriptResult}
        setExpanded={vi.fn()}
      />
    );

    await openMenu();
    await userEvent.click(
      screen.getByRole("button", { name: /view metrics/i })
    );

    expect(mockSendAnalytics).toHaveBeenCalled();
    expect(mockSendAnalytics.mock.calls[0]).toEqual([
      "Machine testing",
      "View testing script metrics",
      "View metrics",
    ]);
  });
});
