import MachineSummary from "./MachineSummary";

import type { RootState } from "@/app/store/root/types";
import { NodeStatusCode } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("MachineSummary", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
      }),
    });
  });

  it("displays a spinner if machines are loading", () => {
    state.machine.items = [];
    renderWithProviders(<MachineSummary />, {
      initialEntries: ["/machine/abc123/summary"],
      pattern: "/machine/:id/summary",
      state,
    });
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("renders", () => {
    renderWithProviders(<MachineSummary />, {
      initialEntries: ["/machine/abc123/summary"],
      pattern: "/machine/:id/summary",
      state,
    });

    expect(screen.getByText("Machine Status")).toBeInTheDocument();
    expect(screen.getByText("CPU")).toBeInTheDocument();
    expect(screen.getByText("Memory")).toBeInTheDocument();
    expect(screen.getByText("Storage")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Zone/i })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Resource pool/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Power type/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tags/i })).toBeInTheDocument();
    expect(screen.getByText("Hardware Information")).toBeInTheDocument();
    expect(screen.getByLabelText("Numa nodes")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Network/i })).toBeInTheDocument();
  });

  it("shows workload annotations for deployed machines", () => {
    state.machine.items = [
      factory.machineDetails({
        status_code: NodeStatusCode.DEPLOYED,
        system_id: "abc123",
      }),
    ];
    renderWithProviders(<MachineSummary />, {
      initialEntries: ["/machine/abc123/summary"],
      pattern: "/machine/:id/summary",
      state,
    });
    expect(screen.getByText("Workload annotations")).toBeInTheDocument();
  });

  it("shows workload annotations for allocated machines", () => {
    state.machine.items = [
      factory.machineDetails({
        status_code: NodeStatusCode.ALLOCATED,
        system_id: "abc123",
      }),
    ];
    renderWithProviders(<MachineSummary />, {
      initialEntries: ["/machine/abc123/summary"],
      pattern: "/machine/:id/summary",
      state,
    });
    expect(screen.getByText("Workload annotations")).toBeInTheDocument();
  });

  it("does not show workload annotations for machines that are neither deployed nor allocated", () => {
    state.machine.items = [
      factory.machineDetails({
        status_code: NodeStatusCode.NEW,
        system_id: "abc123",
      }),
    ];
    renderWithProviders(<MachineSummary />, {
      initialEntries: ["/machine/abc123/summary"],
      pattern: "/machine/:id/summary",
      state,
    });
    expect(screen.queryByText("Workload annotations")).not.toBeInTheDocument();
  });
});
