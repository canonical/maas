import * as reduxToolkit from "@reduxjs/toolkit";

import DeleteTagFormWarnings from "./DeleteTagFormWarnings";

import urls from "@/app/base/urls";
import { FilterMachines } from "@/app/store/machine/utils";
import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

let state: RootState;

const callId = "mocked-nanoid";
vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

beforeEach(() => {
  vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("{}");
  vi.spyOn(query, "generateCallId").mockReturnValue("mocked-nanoid");
  state = factory.rootState({
    machine: factory.machineState({
      items: [
        factory.machine({
          status: NodeStatus.DEPLOYED,
          tags: [1],
        }),
      ],
    }),
    tag: factory.tagState({
      items: [factory.tag({ id: 1 })],
    }),
  });
});

it("does not display a kernel options warning for non-deployed machines", async () => {
  state.tag.items = [
    factory.tag({
      id: 1,
      kernel_opts: "opts",
      machine_count: 4,
      name: "tag1",
    }),
  ];
  state.machine.items = [
    factory.machine({
      status: NodeStatus.ALLOCATED,
      tags: [1],
    }),
  ];
  state.machine.counts = {
    [callId]: factory.machineStateCount({
      count: 0,
      loaded: true,
    }),
  };
  renderWithProviders(<DeleteTagFormWarnings id={1} />, { state });
  expect(
    screen.queryByText(/You are deleting a tag with kernel options/i)
  ).not.toBeInTheDocument();
});

it("displays warning when deleting a tag with kernel options", async () => {
  state.tag.items = [
    factory.tag({
      id: 1,
      kernel_opts: "opts",
      machine_count: 4,
      name: "tag1",
    }),
  ];
  state.machine.counts = {
    [callId]: factory.machineStateCount({
      count: 1,
      loaded: true,
    }),
  };
  renderWithProviders(<DeleteTagFormWarnings id={1} />, { state });
  expect(
    screen.getByText(/You are deleting a tag with kernel options/i)
  ).toBeInTheDocument();
});

it("displays a kernel options warning with multiple machines", async () => {
  state.machine.items.push(
    factory.machine({
      status: NodeStatus.DEPLOYED,
      tags: [1],
    })
  );
  state.tag.items = [
    factory.tag({
      id: 1,
      kernel_opts: "opts",
      machine_count: 4,
      name: "tag1",
    }),
  ];
  state.machine.counts = {
    [callId]: factory.machineStateCount({
      count: 2,
      loaded: true,
    }),
  };
  renderWithProviders(<DeleteTagFormWarnings id={1} />, { state });
  expect(
    screen.getByText(/There are 2 deployed machines with this tag/i)
  ).toBeInTheDocument();
});

it("displays a kernel options warning with one machine", async () => {
  state.tag.items = [
    factory.tag({
      id: 1,
      kernel_opts: "opts",
      machine_count: 1,
      name: "tag1",
    }),
  ];
  state.machine.counts = {
    [callId]: factory.machineStateCount({
      count: 1,
      loaded: true,
    }),
  };
  renderWithProviders(<DeleteTagFormWarnings id={1} />, { state });
  expect(
    screen.getByText(/There is 1 deployed machine with this tag/i)
  ).toBeInTheDocument();
});

it("links to the machine list, filtered by the tag", async () => {
  state.tag.items = [
    factory.tag({
      id: 1,
      kernel_opts: "opts",
      machine_count: 4,
      name: "tag1",
    }),
  ];
  state.machine.counts = {
    [callId]: factory.machineStateCount({
      count: 1,
      loaded: true,
    }),
  };
  renderWithProviders(<DeleteTagFormWarnings id={1} />, { state });
  expect(
    screen.getByRole("link", { name: "Show the deployed machine" })
  ).toHaveAttribute(
    "href",
    `${urls.machines.index}${FilterMachines.filtersToQueryString({ tags: [`=${state.tag.items[0].name}`] })}`
  );
});

it("displays warning when deleting a tag applied to devices", async () => {
  state.tag.items = [
    factory.tag({
      device_count: 1,
      id: 1,
      name: "tag1",
    }),
  ];
  renderWithProviders(<DeleteTagFormWarnings id={1} />, { state });
  expect(
    screen.getByText(/There is 1 device with this tag/i)
  ).toBeInTheDocument();
});

it("displays warning when deleting a tag applied to controllers", async () => {
  state.tag.items = [
    factory.tag({
      controller_count: 1,
      id: 1,
      name: "tag1",
    }),
  ];
  renderWithProviders(<DeleteTagFormWarnings id={1} />, { state });
  expect(
    screen.getByText(/There is 1 controller with this tag/i)
  ).toBeInTheDocument();
});

it("generates the correct sentence for multiple nodes", async () => {
  state.tag.items = [
    factory.tag({
      controller_count: 2,
      id: 1,
      name: "tag1",
    }),
  ];
  renderWithProviders(<DeleteTagFormWarnings id={1} />, { state });
  expect(
    screen.getByText(/There are 2 controllers with this tag/i)
  ).toBeInTheDocument();
});
