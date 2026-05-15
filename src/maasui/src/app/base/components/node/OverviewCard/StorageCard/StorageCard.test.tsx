import { screen } from "@testing-library/react";

import StorageCard from "./StorageCard";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

let state: RootState;
beforeEach(() => {
  state = factory.rootState({
    controller: factory.controllerState({
      items: [],
    }),
    machine: factory.machineState(),
  });
});

it("does not render test info if node is a controller", () => {
  const controller = factory.controllerDetails();
  state.controller.items = [controller];

  renderWithProviders(<StorageCard node={controller} />, { state });

  expect(screen.queryByTestId("tests")).not.toBeInTheDocument();
});

it("renders test info if node is a machine", () => {
  const machine = factory.machineDetails();
  state.machine.items = [machine];

  renderWithProviders(<StorageCard node={machine} />, { state });

  expect(screen.getByTestId("tests")).toBeInTheDocument();
});

describe("node is a machine", () => {
  it("renders a link with a count of passed tests", () => {
    const machine = factory.machineDetails();
    machine.storage_test_status = factory.testStatus({
      passed: 2,
    });
    state.machine.items = [machine];

    renderWithProviders(<StorageCard node={machine} />, { state });

    expect(screen.getByText(/2/i)).toBeInTheDocument();
  });

  it("renders a link with a count of pending and running tests", () => {
    const machine = factory.machineDetails();
    machine.storage_test_status = factory.testStatus({
      running: 1,
      pending: 2,
    });
    state.machine.items = [machine];

    renderWithProviders(<StorageCard node={machine} />, { state });

    expect(screen.getByText(/3/i)).toBeInTheDocument();
  });

  it("renders a link with a count of failed tests", () => {
    const machine = factory.machineDetails();
    machine.storage_test_status = factory.testStatus({
      failed: 5,
    });
    state.machine.items = [machine];

    renderWithProviders(<StorageCard node={machine} />, { state });

    expect(screen.getByText(/5/i)).toBeInTheDocument();
  });

  it("renders a results link", () => {
    const machine = factory.machineDetails();
    machine.storage_test_status = factory.testStatus({
      failed: 5,
    });
    state.machine.items = [machine];

    renderWithProviders(<StorageCard node={machine} />, { state });

    expect(screen.getByText(/view results/i)).toBeInTheDocument();
  });

  it("renders a test storage link if no tests run", () => {
    const machine = factory.machineDetails();
    machine.storage_test_status = factory.testStatus();
    state.machine.items = [machine];

    renderWithProviders(<StorageCard node={machine} />, { state });

    expect(screen.getByText(/test storage/i)).toBeInTheDocument();
  });
});
