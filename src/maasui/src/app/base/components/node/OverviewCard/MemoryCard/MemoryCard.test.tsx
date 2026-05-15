import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import MemoryCard from "./MemoryCard";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

let state: RootState;
beforeEach(() => {
  state = factory.rootState({
    controller: factory.controllerState({
      items: [],
    }),
    machine: factory.machineState({
      items: [],
    }),
  });
});

it("does not render test info if node is a controller", () => {
  const controller = factory.controllerDetails();
  state.controller.items = [controller];

  renderWithProviders(<MemoryCard node={controller} />, {
    state,
  });

  expect(screen.queryByText(/tests/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/test memory/i)).not.toBeInTheDocument();
});

it("renders test info if node is a machine", async () => {
  const machine = factory.machineDetails();
  state.machine.items = [machine];

  renderWithProviders(<MemoryCard node={machine} />, {
    state,
  });

  await userEvent.click(screen.getByRole("button", { name: /test memory/i }));
  expect(screen.getByText(/tests/i)).toBeInTheDocument();
});

describe("node is a machine", () => {
  it("renders a link with a count of passed tests", () => {
    const machine = factory.machineDetails();
    machine.memory_test_status = factory.testStatus({
      passed: 2,
    });
    state.machine.items = [machine];

    renderWithProviders(<MemoryCard node={machine} />, {
      state,
    });

    expect(screen.getByRole("link", { name: /2/i })).toBeInTheDocument();
  });

  it("renders a link with a count of pending and running tests", () => {
    const machine = factory.machineDetails();
    machine.memory_test_status = factory.testStatus({
      running: 1,
      pending: 2,
    });
    state.machine.items = [machine];

    renderWithProviders(<MemoryCard node={machine} />, {
      state,
    });

    expect(screen.getByRole("link", { name: /3/i })).toBeInTheDocument();
  });

  it("renders a link with a count of failed tests", () => {
    const machine = factory.machineDetails();
    machine.memory_test_status = factory.testStatus({
      failed: 5,
    });
    state.machine.items = [machine];

    renderWithProviders(<MemoryCard node={machine} />, {
      state,
    });

    expect(screen.getByRole("link", { name: /5/i })).toBeInTheDocument();
  });

  it("renders a results link", () => {
    const machine = factory.machineDetails();
    machine.memory_test_status = factory.testStatus({
      failed: 5,
    });
    state.machine.items = [machine];

    renderWithProviders(<MemoryCard node={machine} />, {
      state,
    });

    expect(
      screen.getByRole("link", { name: /view results/i })
    ).toBeInTheDocument();
  });

  it("renders a test cpu link if no tests run", () => {
    const machine = factory.machineDetails();
    machine.memory_test_status = factory.testStatus();
    state.machine.items = [machine];

    renderWithProviders(<MemoryCard node={machine} />, {
      state,
    });

    expect(
      screen.getByRole("button", { name: /test memory/i })
    ).toBeInTheDocument();
  });
});
