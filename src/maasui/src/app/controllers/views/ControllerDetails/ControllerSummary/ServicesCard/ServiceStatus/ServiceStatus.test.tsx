import ServiceStatus from "./ServiceStatus";

import {
  ServiceName,
  ServiceStatus as ServiceStatusName,
} from "@/app/store/service/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("correctly renders a running service", () => {
  const service = factory.service({ status: ServiceStatusName.RUNNING });
  renderWithProviders(<ServiceStatus service={service} />);

  expect(screen.getByTestId("service-status-icon")).toHaveClass(
    "p-icon--success"
  );
  expect(screen.getByTestId("service-status-icon")).toHaveAccessibleName(
    ServiceStatusName.RUNNING
  );
});

it("correctly renders a degraded service", () => {
  const service = factory.service({ status: ServiceStatusName.DEGRADED });
  renderWithProviders(<ServiceStatus service={service} />);

  expect(screen.getByTestId("service-status-icon")).toHaveClass(
    "p-icon--warning"
  );
  expect(screen.getByTestId("service-status-icon")).toHaveAccessibleName(
    ServiceStatusName.DEGRADED
  );
});

it("correctly renders a dead service", () => {
  const service = factory.service({ status: ServiceStatusName.DEAD });
  renderWithProviders(<ServiceStatus service={service} />);

  expect(screen.getByTestId("service-status-icon")).toHaveClass(
    "p-icon--error"
  );
  expect(screen.getByTestId("service-status-icon")).toHaveAccessibleName(
    ServiceStatusName.DEAD
  );
});

it("correctly renders an unknown service", () => {
  const service = factory.service({ status: ServiceStatusName.UNKNOWN });
  renderWithProviders(<ServiceStatus service={service} />);

  expect(screen.queryByTestId("service-status-icon")).not.toBeInTheDocument();
});

it("renders additional status info if provided", () => {
  const service = factory.service({
    name: ServiceName.BIND9,
    status: ServiceStatusName.UNKNOWN,
    status_info: "I have no idea what this is",
  });
  renderWithProviders(<ServiceStatus service={service} />);

  expect(screen.getByText(/I have no idea what this is/i)).toBeInTheDocument();
});
