import ServicesCard from "./ServicesCard";

import { serviceActions } from "@/app/store/service";
import { ServiceName, ServiceStatus } from "@/app/store/service/types";
import { getServiceDisplayName } from "@/app/store/service/utils";
import { NodeType } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("fetches services on load", () => {
  const controller = factory.controllerDetails();
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
  });

  const { store } = renderWithProviders(
    <ServicesCard controller={controller} />,
    { state }
  );

  const expectedAction = serviceActions.fetch();
  expect(
    store.getActions().find((action) => action.type === expectedAction.type)
  ).toStrictEqual(expectedAction);
});

it("shows a spinner if services are loading", () => {
  const controller = factory.controllerDetails();
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
    service: factory.serviceState({
      loading: true,
    }),
  });

  renderWithProviders(<ServicesCard controller={controller} />, { state });

  expect(
    screen.getByRole("alert", { name: "Loading services" })
  ).toBeInTheDocument();
});

it("renders the title correctly when at least one service is dead", () => {
  const services = [
    factory.service({ status: ServiceStatus.DEAD }),
    factory.service({ status: ServiceStatus.DEGRADED }),
    factory.service({ status: ServiceStatus.DEGRADED }),
    factory.service({ status: ServiceStatus.RUNNING }),
    factory.service({ status: ServiceStatus.RUNNING }),
    factory.service({ status: ServiceStatus.RUNNING }),
    factory.service({ status: ServiceStatus.OFF }),
    factory.service({ status: ServiceStatus.UNKNOWN }),
  ];
  const controller = factory.controllerDetails({
    service_ids: services.map(({ id }) => id),
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
    service: factory.serviceState({
      items: services,
    }),
  });

  renderWithProviders(<ServicesCard controller={controller} />, { state });

  expect(screen.getByTestId("title")).toHaveTextContent(
    "1 dead, 2 degraded, 3 running"
  );
  expect(screen.getByTestId("title-icon")).toHaveAccessibleName("error");
});

it("renders the title corectly when at least one service is degraded and none are dead", () => {
  const services = [
    factory.service({ status: ServiceStatus.DEGRADED }),
    factory.service({ status: ServiceStatus.RUNNING }),
    factory.service({ status: ServiceStatus.RUNNING }),
    factory.service({ status: ServiceStatus.OFF }),
    factory.service({ status: ServiceStatus.UNKNOWN }),
  ];
  const controller = factory.controllerDetails({
    service_ids: services.map(({ id }) => id),
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
    service: factory.serviceState({
      items: services,
    }),
  });
  renderWithProviders(<ServicesCard controller={controller} />, { state });

  expect(screen.getByTestId("title")).toHaveTextContent(
    "1 degraded, 2 running"
  );
  expect(screen.getByTestId("title-icon")).toHaveAccessibleName("warning");
});

it("renders the title corectly when at least one service is running and none are dead or degraded", () => {
  const services = [
    factory.service({ status: ServiceStatus.RUNNING }),
    factory.service({ status: ServiceStatus.OFF }),
    factory.service({ status: ServiceStatus.UNKNOWN }),
  ];
  const controller = factory.controllerDetails({
    service_ids: services.map(({ id }) => id),
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
    service: factory.serviceState({
      items: services,
    }),
  });
  renderWithProviders(<ServicesCard controller={controller} />, { state });

  expect(screen.getByTestId("title")).toHaveTextContent("1 running");
  expect(screen.getByTestId("title-icon")).toHaveAccessibleName("success");
});

it("only renders rack controller services for a rack controller", () => {
  const services = [
    factory.service({ name: ServiceName.RACKD }),
    factory.service({ name: ServiceName.REGIOND }),
    factory.service({ name: ServiceName.REVERSE_PROXY }),
  ];
  const controller = factory.controllerDetails({
    node_type: NodeType.RACK_CONTROLLER,
    service_ids: services.map(({ id }) => id),
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
    service: factory.serviceState({
      items: services,
    }),
  });
  renderWithProviders(<ServicesCard controller={controller} />, { state });

  expect(
    screen.getByText(getServiceDisplayName(ServiceName.RACKD))
  ).toBeInTheDocument();
  expect(
    screen.queryByText(getServiceDisplayName(ServiceName.REGIOND))
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText(getServiceDisplayName(ServiceName.REVERSE_PROXY))
  ).not.toBeInTheDocument();
});

it("only renders region controller services for a region controller", () => {
  const services = [
    factory.service({ name: ServiceName.RACKD }),
    factory.service({ name: ServiceName.REGIOND }),
    factory.service({ name: ServiceName.REVERSE_PROXY }),
  ];
  const controller = factory.controllerDetails({
    node_type: NodeType.REGION_CONTROLLER,
    service_ids: services.map(({ id }) => id),
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
    service: factory.serviceState({
      items: services,
    }),
  });

  renderWithProviders(<ServicesCard controller={controller} />, { state });

  expect(
    screen.getByText(getServiceDisplayName(ServiceName.REGIOND))
  ).toBeInTheDocument();
  expect(
    screen.getByText(getServiceDisplayName(ServiceName.REVERSE_PROXY))
  ).toBeInTheDocument();
  expect(
    screen.queryByText(getServiceDisplayName(ServiceName.RACKD))
  ).not.toBeInTheDocument();
});

it("renders both region and rack controller services for a region+rack controller", () => {
  const services = [
    factory.service({ name: ServiceName.RACKD }),
    factory.service({ name: ServiceName.REGIOND }),
    factory.service({ name: ServiceName.REVERSE_PROXY }),
  ];
  const controller = factory.controllerDetails({
    node_type: NodeType.REGION_AND_RACK_CONTROLLER,
    service_ids: services.map(({ id }) => id),
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
    service: factory.serviceState({
      items: services,
    }),
  });

  renderWithProviders(<ServicesCard controller={controller} />, { state });

  expect(
    screen.getByText(getServiceDisplayName(ServiceName.REGIOND))
  ).toBeInTheDocument();
  expect(
    screen.getByText(getServiceDisplayName(ServiceName.RACKD))
  ).toBeInTheDocument();
  expect(
    screen.getByText(getServiceDisplayName(ServiceName.REVERSE_PROXY))
  ).toBeInTheDocument();
});
