import DetailsCard, { Labels as DetailsCardLabels } from "./DetailsCard";

import urls from "@/app/base/urls";
import { PowerTypeNames } from "@/app/store/general/constants";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

let state: RootState;
beforeEach(() => {
  state = factory.rootState({
    controller: factory.controllerState({
      items: [],
    }),
    machine: factory.machineState({
      items: [],
    }),
    general: factory.generalState({
      powerTypes: factory.powerTypesState({
        data: [],
        loaded: true,
      }),
    }),
  });
});

it("renders a link to zone configuration with edit permissions", () => {
  const machine = factory.machineDetails({
    permissions: ["edit"],
    zone: { id: 1, name: "danger" },
  });
  state.machine.items = [machine];

  renderWithProviders(<DetailsCard node={machine} />, {
    state,
  });

  expect(
    screen.getByRole("link", { name: DetailsCardLabels.ZoneLink })
  ).toBeInTheDocument();
  expect(screen.getByText("danger")).toBeInTheDocument();
});

it("renders a zone label without edit permissions", () => {
  const machine = factory.machineDetails({
    permissions: [],
    zone: { id: 1, name: "danger" },
  });
  state.machine.items = [machine];

  renderWithProviders(<DetailsCard node={machine} />, {
    state,
  });

  expect(
    screen.queryByRole("link", { name: DetailsCardLabels.ZoneLink })
  ).not.toBeInTheDocument();
  expect(screen.getByText(DetailsCardLabels.Zone)).toBeInTheDocument();
  expect(screen.getByText("danger")).toBeInTheDocument();
});

it("renders a formatted power type", () => {
  const machine = factory.machineDetails({
    power_type: PowerTypeNames.LXD,
  });
  const powerType = factory.powerType({
    name: PowerTypeNames.LXD,
    description: "LXD (virtual systems)",
  });
  state.machine.items = [machine];
  state.general.powerTypes.data = [powerType];

  renderWithProviders(<DetailsCard node={machine} />, {
    state,
  });

  expect(
    screen.getByRole("link", { name: DetailsCardLabels.PowerTypeLink })
  ).toBeInTheDocument();
  expect(screen.getByText("LXD")).toBeInTheDocument();
});

it("shows a spinner if tags are not loaded", () => {
  const machine = factory.machineDetails({ tags: [1] });
  const state = factory.rootState({
    machine: factory.machineState({
      items: [machine],
    }),
    tag: factory.tagState({
      items: [],
      loaded: false,
    }),
  });

  renderWithProviders(<DetailsCard node={machine} />, {
    state,
  });

  expect(screen.getByText("Loading")).toBeInTheDocument();
});

it("renders a list of tags once loaded", () => {
  const machine = factory.machineDetails({ tags: [1, 2, 3] });
  const tags = [
    factory.tag({ id: 1, name: "virtual" }),
    factory.tag({ id: 2, name: "test" }),
    factory.tag({ id: 3, name: "lxd" }),
  ];
  const state = factory.rootState({
    machine: factory.machineState({
      items: [machine],
    }),
    tag: factory.tagState({
      items: tags,
      loaded: true,
    }),
  });

  renderWithProviders(<DetailsCard node={machine} />, {
    state,
  });

  expect(screen.getByText("lxd, test, virtual")).toBeInTheDocument();
});

describe("node is a controller", () => {
  it("does not render owner, host, pool, or kernel crash dump information", () => {
    const controller = factory.controllerDetails();
    state.controller.items = [controller];

    renderWithProviders(<DetailsCard node={controller} />, {
      state,
    });

    expect(screen.queryByText(DetailsCardLabels.Owner)).not.toBeInTheDocument();
    expect(screen.queryByText(DetailsCardLabels.Host)).not.toBeInTheDocument();
    expect(
      screen.queryByText(DetailsCardLabels.PoolLink)
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(DetailsCardLabels.KernelCrashDump)
    ).not.toBeInTheDocument();
  });
});

describe("node is a machine", () => {
  it("renders the owner", () => {
    const machine = factory.machineDetails({ owner: "admin" });
    state.machine.items = [machine];

    renderWithProviders(<DetailsCard node={machine} />, {
      state,
    });

    expect(screen.getByText(DetailsCardLabels.Owner)).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("renders host details for LXD machines", () => {
    const machine = factory.machineDetails({
      pod: { id: 1, name: "lxd-pod" },
      power_type: PowerTypeNames.LXD,
    });
    const pod = factory.pod({
      id: 1,
      name: "lxd-pod",
      type: PodType.LXD,
    });

    state.machine.items = [machine];
    state.pod.items = [pod];

    renderWithProviders(<DetailsCard node={machine} />, {
      state,
    });

    expect(screen.getByText(DetailsCardLabels.Owner)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "lxd-pod ›" })).toHaveAttribute(
      "href",
      urls.kvm.lxd.single.index({ id: pod.id })
    );
  });

  it("renders host details for virsh machines", () => {
    const machine = factory.machineDetails({
      pod: { id: 1, name: "virsh-pod" },
      power_type: PowerTypeNames.VIRSH,
    });
    const pod = factory.pod({
      id: 1,
      name: "virsh-pod",
      type: PodType.VIRSH,
    });

    state.machine.items = [machine];
    state.pod.items = [pod];

    renderWithProviders(<DetailsCard node={machine} />, {
      state,
    });

    expect(screen.getByText(DetailsCardLabels.Host)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "virsh-pod ›" })).toHaveAttribute(
      "href",
      urls.kvm.virsh.details.index({ id: pod.id })
    );
  });

  it("renders a link to resource pool configuration with edit permissions", () => {
    const machine = factory.machineDetails({
      permissions: ["edit"],
      pool: { id: 1, name: "swimming" },
    });
    state.machine.items = [machine];

    renderWithProviders(<DetailsCard node={machine} />, {
      state,
    });

    expect(
      screen.getByRole("link", { name: DetailsCardLabels.PoolLink })
    ).toBeInTheDocument();
    expect(screen.getByText("swimming")).toBeInTheDocument();
  });

  it("renders a resource pool label without edit permissions", () => {
    const machine = factory.machineDetails({
      permissions: [],
      pool: { id: 1, name: "swimming" },
    });
    state.machine.items = [machine];

    renderWithProviders(<DetailsCard node={machine} />, {
      state,
    });

    expect(
      screen.queryByRole("link", { name: DetailsCardLabels.PoolLink })
    ).not.toBeInTheDocument();
    expect(screen.getByText(DetailsCardLabels.Pool)).toBeInTheDocument();
    expect(screen.getByText("swimming")).toBeInTheDocument();
  });

  it("shows the status of kernel crash dumps on the machine", () => {
    const machine = factory.machineDetails({
      enable_kernel_crash_dump: true,
    });
    state.machine.items = [machine];

    renderWithProviders(<DetailsCard node={machine} />, {
      state,
    });

    expect(
      screen.getByText(DetailsCardLabels.KernelCrashDump)
    ).toBeInTheDocument();
    expect(screen.getByText("enabled")).toBeInTheDocument();
  });
});
