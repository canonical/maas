/* eslint-disable testing-library/no-node-access */

import { render, screen } from "@testing-library/react";

import ScriptStatus from "./ScriptStatus";

import { ScriptResultStatus } from "@/app/store/scriptresult/types";
import { expectTooltipOnHover, renderWithProviders } from "@/testing/utils";

const getIcon = (name: string, container: HTMLElement): Element | null => {
  return container.querySelector(`.p-icon--${name}`);
};

describe("ScriptStatus", () => {
  it("can show a passed icon", () => {
    const { container } = render(
      <ScriptStatus status={ScriptResultStatus.PASSED} />
    );

    expect(getIcon("success", container)).toBeInTheDocument();
  });

  it("can show a pending icon", () => {
    const { container } = render(
      <ScriptStatus status={ScriptResultStatus.PENDING} />
    );
    expect(getIcon("pending", container)).toBeInTheDocument();
  });

  it("can show a running icon", () => {
    const { container } = render(
      <ScriptStatus status={ScriptResultStatus.RUNNING} />
    );
    expect(getIcon("running", container)).toBeInTheDocument();
  });

  it("can show a failed icon", () => {
    const { container } = render(
      <ScriptStatus status={ScriptResultStatus.FAILED} />
    );
    expect(getIcon("error", container)).toBeInTheDocument();
  });

  it("can show a timed out icon", () => {
    const { container } = render(
      <ScriptStatus status={ScriptResultStatus.TIMEDOUT} />
    );
    expect(getIcon("timed-out", container)).toBeInTheDocument();
  });

  it("can show a skipped icon", () => {
    const { container } = render(
      <ScriptStatus status={ScriptResultStatus.SKIPPED} />
    );
    expect(getIcon("warning", container)).toBeInTheDocument();
  });

  it("makes the icon inline if children are provided", () => {
    const { container } = render(
      <ScriptStatus status={ScriptResultStatus.PASSED}>{0}</ScriptStatus>
    );
    expect(getIcon("success", container)).toHaveClass("is-inline");
  });

  it("does not make the icon inline if children are not provided", () => {
    const { container } = render(
      <ScriptStatus status={ScriptResultStatus.PASSED} />
    );
    expect(getIcon("success", container)).not.toHaveClass("is-inline");
  });

  it("can have its icon wrapped in a tooltip", async () => {
    renderWithProviders(
      <ScriptStatus
        status={ScriptResultStatus.PASSED}
        tooltipMessage="Tooltip!"
        tooltipPosition="top-right"
      />
    );
    await expectTooltipOnHover(screen.getByRole("button"), "Tooltip!");
  });
});
