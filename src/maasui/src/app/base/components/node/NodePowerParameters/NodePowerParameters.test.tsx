import NodePowerParameters from "./NodePowerParameters";

import { PowerTypeNames } from "@/app/store/general/constants";
import { PowerFieldScope } from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

let state: RootState;
beforeEach(() => {
  state = factory.rootState({
    general: factory.generalState({
      powerTypes: factory.powerTypesState({
        data: [factory.powerType({ fields: [], name: PowerTypeNames.MANUAL })],
        loaded: true,
      }),
    }),
  });
});

it("shows an error if no rack controller is connected", () => {
  state.general.powerTypes.data = [];
  const machine = factory.machineDetails({ system_id: "abc123" });

  renderWithProviders(<NodePowerParameters node={machine} />, { state });

  expect(
    screen.getByText(/no rack controller is currently connected/)
  ).toBeInTheDocument();
});

it("shows an error if a power type has not been set", () => {
  const machine = factory.machineDetails({
    power_type: "",
    system_id: "abc123",
  });

  renderWithProviders(<NodePowerParameters node={machine} />, { state });

  expect(
    screen.getByText(/This node does not have a power type set/)
  ).toBeInTheDocument();
});

it("shows a warning if the power type is set to manual", () => {
  const machine = factory.machineDetails({
    power_type: PowerTypeNames.MANUAL,
    system_id: "abc123",
  });

  renderWithProviders(<NodePowerParameters node={machine} />, { state });

  expect(
    screen.getByText(
      /Power control for this power type will need to be handled manually/
    )
  ).toBeInTheDocument();
});

it("shows an error if the power type is missing packages", () => {
  state.general.powerTypes.data = [
    factory.powerType({
      description: "AMT",
      missing_packages: ["package1", "package2"],
      name: PowerTypeNames.AMT,
    }),
  ];
  const machine = factory.machineDetails({
    power_type: PowerTypeNames.AMT,
    system_id: "abc123",
  });

  renderWithProviders(<NodePowerParameters node={machine} />, { state });

  expect(
    screen.getByText(
      /Power control software for AMT is missing from the rack controller. /
    )
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      /To proceed, install the following packages on the rack controller: package1, package2/
    )
  ).toBeInTheDocument();
});

it("renders power parameters for all scopes if machine is not in a pod", () => {
  state.general.powerTypes.data = [
    factory.powerType({
      fields: [
        factory.powerField({ name: "node-field", scope: PowerFieldScope.NODE }),
        factory.powerField({ name: "bmc-field", scope: PowerFieldScope.BMC }),
      ],
      name: PowerTypeNames.LXD,
    }),
  ];
  const machine = factory.machineDetails({
    pod: undefined,
    power_parameters: {
      "node-field": "node field",
      "bmc-field": "bmc field",
    },
    power_type: PowerTypeNames.LXD,
    system_id: "abc123",
  });

  renderWithProviders(<NodePowerParameters node={machine} />, { state });

  expect(screen.getByText("node field")).toBeInTheDocument();
  expect(screen.getByText("bmc field")).toBeInTheDocument();
});

it("renders power parameters only for node scope if machine is in a pod", () => {
  state.general.powerTypes.data = [
    factory.powerType({
      fields: [
        factory.powerField({ name: "node-field", scope: PowerFieldScope.NODE }),
        factory.powerField({ name: "bmc-field", scope: PowerFieldScope.BMC }),
      ],
      name: PowerTypeNames.LXD,
    }),
  ];
  const machine = factory.machineDetails({
    pod: factory.modelRef(),
    power_parameters: {
      "node-field": "node field",
      "bmc-field": "bmc field",
    },
    power_type: PowerTypeNames.LXD,
    system_id: "abc123",
  });

  renderWithProviders(<NodePowerParameters node={machine} />, { state });

  expect(screen.getByText("node field")).toBeInTheDocument();
  expect(screen.queryByText("bmc field")).not.toBeInTheDocument();
});

it("renders certificate power parameters with metadata", () => {
  const certificateMetadata = factory.certificateMetadata();
  state.general.powerTypes.data = [
    factory.powerType({
      fields: [factory.powerField({ name: "certificate" })],
      name: PowerTypeNames.LXD,
    }),
  ];
  const machine = factory.machineDetails({
    certificate: certificateMetadata,
    power_parameters: {
      certificate: "abc",
    },
    power_type: PowerTypeNames.LXD,
    system_id: "abc123",
  });

  renderWithProviders(<NodePowerParameters node={machine} />, { state });

  expect(screen.getByText(certificateMetadata.CN)).toBeInTheDocument();
  expect(screen.getByText(certificateMetadata.expiration)).toBeInTheDocument();
  expect(screen.getByText(certificateMetadata.fingerprint)).toBeInTheDocument();
  expect(screen.getByRole("textbox")).toHaveValue("abc");
});

it("renders power parameters for a controller", () => {
  state.general.powerTypes.data = [
    factory.powerType({
      fields: [
        factory.powerField({ name: "node-field", scope: PowerFieldScope.NODE }),
        factory.powerField({ name: "bmc-field", scope: PowerFieldScope.BMC }),
      ],
      name: PowerTypeNames.LXD,
    }),
  ];
  const controller = factory.controllerDetails({
    power_parameters: {
      "node-field": "node field",
      "bmc-field": "bmc field",
    },
    power_type: PowerTypeNames.LXD,
    system_id: "abc123",
  });

  renderWithProviders(<NodePowerParameters node={controller} />, { state });

  expect(screen.getByText("node field")).toBeInTheDocument();
  expect(screen.getByText("bmc field")).toBeInTheDocument();
});
