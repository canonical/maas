import { screen } from "@testing-library/react";

import CpuCard from "./CpuCard";

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

it("renders the cpu subtext", () => {
  const machine = factory.machineDetails({ cpu_speed: 2000 });
  state.machine.items = [machine];
  renderWithProviders(<CpuCard node={machine} />, { state });
  expect(screen.getByTestId("cpu-subtext")).toHaveTextContent(
    `${machine.cpu_count} core, 2 GHz`
  );
});

it("renders the cpu subtext for slower CPUs", () => {
  const machine = factory.machineDetails({ cpu_speed: 200 });
  state.machine.items = [machine];
  renderWithProviders(<CpuCard node={machine} />, { state });
  expect(screen.getByTestId("cpu-subtext")).toHaveTextContent(
    `${machine.cpu_count} core, 200 MHz`
  );
});

it("does not render test info if node is a controller", () => {
  const controller = factory.controllerDetails();
  state.controller.items = [controller];
  renderWithProviders(<CpuCard node={controller} />, { state });
  expect(screen.queryByTestId("tests")).not.toBeInTheDocument();
});

it("renders test info if node is a machine", () => {
  const machine = factory.machineDetails();
  state.machine.items = [machine];
  renderWithProviders(<CpuCard node={machine} />, { state });
  expect(screen.getByTestId("tests")).toBeInTheDocument();
});

describe("node is a machine", () => {
  it("renders a link with a count of passed tests", () => {
    const machine = factory.machineDetails();
    machine.cpu_test_status = factory.testStatus({
      passed: 2,
    });
    state.machine.items = [machine];
    renderWithProviders(<CpuCard node={machine} />, { state });
    expect(screen.getByRole("link", { name: "2" })).toBeInTheDocument();
  });

  it("renders a link with a count of pending and running tests", () => {
    const machine = factory.machineDetails();
    machine.cpu_test_status = factory.testStatus({
      running: 1,
      pending: 2,
    });
    state.machine.items = [machine];
    renderWithProviders(<CpuCard node={machine} />, { state });
    expect(screen.getByRole("link", { name: "3" })).toBeInTheDocument();
  });

  it("renders a link with a count of failed tests", () => {
    const machine = factory.machineDetails();
    machine.cpu_test_status = factory.testStatus({
      failed: 5,
    });
    state.machine.items = [machine];
    renderWithProviders(<CpuCard node={machine} />, { state });
    expect(screen.getByRole("link", { name: "5" })).toBeInTheDocument();
  });

  it("renders a results link", () => {
    const machine = factory.machineDetails();
    machine.cpu_test_status = factory.testStatus({
      failed: 5,
    });
    state.machine.items = [machine];
    renderWithProviders(<CpuCard node={machine} />, { state });
    expect(
      screen.getByRole("link", { name: /View results/ })
    ).toBeInTheDocument();
  });

  it("renders a test cpu link if no tests run", () => {
    const machine = factory.machineDetails();
    machine.cpu_test_status = factory.testStatus();
    state.machine.items = [machine];
    renderWithProviders(<CpuCard node={machine} />, { state });
    expect(
      screen.getByRole("button", { name: /Test CPU/ })
    ).toBeInTheDocument();
  });
});
