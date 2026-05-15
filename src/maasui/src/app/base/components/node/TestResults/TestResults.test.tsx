import { screen } from "@testing-library/react";

import TestResults from "./TestResults";

import { HardwareType } from "@/app/base/enum";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

describe("TestResults", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState(),
    });
  });

  it("renders a link with a count of passed cpu tests", () => {
    const machine = factory.machineDetails();
    machine.cpu_test_status = factory.testStatus({
      passed: 2,
    });
    state.machine.items = [machine];

    renderWithProviders(
      <TestResults hardwareType={HardwareType.CPU} machine={machine} />,
      {
        state,
      }
    );

    expect(screen.getByRole("link", { name: "2" })).toBeInTheDocument();
  });

  it("renders a link with a count of pending and running memory tests", () => {
    const machine = factory.machineDetails();
    machine.memory_test_status = factory.testStatus({
      running: 1,
      pending: 2,
    });
    state.machine.items = [machine];

    renderWithProviders(
      <TestResults hardwareType={HardwareType.Memory} machine={machine} />,
      {
        state,
      }
    );

    expect(screen.getByRole("link", { name: "3" })).toBeInTheDocument();
  });

  it("renders a link with a count of failed storage tests", () => {
    const machine = factory.machineDetails();
    machine.storage_test_status = factory.testStatus({
      failed: 5,
    });
    state.machine.items = [machine];

    renderWithProviders(
      <TestResults hardwareType={HardwareType.Storage} machine={machine} />,
      {
        state,
      }
    );

    expect(screen.getByRole("link", { name: "5" })).toBeInTheDocument();
  });

  it("renders a results link", () => {
    const machine = factory.machineDetails();
    machine.cpu_test_status = factory.testStatus({
      failed: 5,
    });
    state.machine.items = [machine];

    renderWithProviders(
      <TestResults hardwareType={HardwareType.CPU} machine={machine} />,
      {
        state,
      }
    );

    expect(
      screen.getByRole("link", { name: /View results/i })
    ).toBeInTheDocument();
  });

  it("renders a test network link if no tests run", () => {
    const machine = factory.machineDetails();
    machine.network_test_status = factory.testStatus();
    state.machine.items = [machine];

    renderWithProviders(
      <TestResults hardwareType={HardwareType.Network} machine={machine} />,
      {
        state,
      }
    );

    expect(
      screen.getByRole("button", { name: /Test network/i })
    ).toBeInTheDocument();
  });
});
