import AddLxd from "./AddLxd";

import { ConfigNames } from "@/app/store/config/types";
import { podActions } from "@/app/store/pod";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  poolsResolvers.listPools.handler(),
  zoneResolvers.listZones.handler()
);

describe("AddLxd", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [{ name: ConfigNames.MAAS_NAME, value: "MAAS" }],
      }),
      general: factory.generalState({
        generatedCertificate: factory.generatedCertificateState({
          data: null,
        }),
        powerTypes: factory.powerTypesState({
          data: [
            factory.powerType({
              name: PodType.LXD,
              fields: [
                factory.powerField({ name: "power_address" }),
                factory.powerField({ name: "password" }),
              ],
            }),
          ],
          loaded: true,
        }),
      }),
      pod: factory.podState({
        loaded: true,
      }),
    });
  });

  it("shows the credentials form by default", () => {
    renderWithProviders(<AddLxd />, {
      initialEntries: ["/kvm/add"],
      state,
    });

    expect(screen.getByText("Credentials")).toHaveClass(
      "stepper__title--is-active"
    );
    expect(screen.getByText("Authentication")).not.toHaveClass(
      "stepper__title--is-active"
    );
    expect(screen.getByText("Project selection")).not.toHaveClass(
      "stepper__title--is-active"
    );
  });

  it(`shows the authentication form if the user has generated a certificate for
    the LXD KVM host`, async () => {
    state.general.generatedCertificate.data = factory.generatedCertificate({
      CN: "my-favourite-kvm@host",
    });

    renderWithProviders(<AddLxd />, {
      initialEntries: ["/kvm/add"],
      state,
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });

    // Submit credentials form
    await userEvent.type(
      screen.getByRole("textbox", { name: "Name" }),
      "my-favourite-kvm"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Resource pool" }),
      "1"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Zone" }),
      "1"
    );
    await userEvent.type(
      screen.getByRole("combobox", { name: "LXD address" }),
      "192.168.1.1"
    );
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(
        screen.getByRole("listitem", { name: "Credentials" }).firstChild
      ).not.toHaveClass("stepper__title--is-active");
    });
    expect(
      screen.getByRole("listitem", { name: "Authentication" }).firstChild
    ).toHaveClass("stepper__title--is-active");
    expect(
      screen.getByRole("listitem", { name: "Project selection" }).firstChild
    ).not.toHaveClass("stepper__title--is-active");

    expect(
      screen.queryByRole("form", { name: "Credentials" })
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("form", { name: "Authentication" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("form", { name: "Project selection" })
    ).not.toBeInTheDocument();
  });

  it("shows the project select form once authenticated", async () => {
    state.pod.projects = {
      "192.168.1.1": [factory.podProject()],
    };

    renderWithProviders(<AddLxd />, {
      initialEntries: ["/kvm/add"],
      state,
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });

    // Submit credentials form
    await userEvent.type(
      screen.getByRole("textbox", { name: "Name" }),
      "my-favourite-kvm"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Resource pool" }),
      "1"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Zone" }),
      "1"
    );
    await userEvent.type(
      screen.getByRole("combobox", { name: "LXD address" }),
      "192.168.1.1"
    );
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(
        screen.getByRole("listitem", { name: "Credentials" }).firstChild
      ).not.toHaveClass("stepper__title--is-active");
    });
    expect(
      screen.getByRole("listitem", { name: "Authentication" }).firstChild
    ).not.toHaveClass("stepper__title--is-active");
    expect(
      screen.getByRole("listitem", { name: "Project selection" }).firstChild
    ).toHaveClass("stepper__title--is-active");
  });

  it("clears projects and runs cleanup on unmount", () => {
    const {
      result: { unmount },
      store,
    } = renderWithProviders(<AddLxd />, {
      initialEntries: ["/kvm/add"],
      state,
    });

    unmount();

    const expectedActions = [podActions.cleanup(), podActions.clearProjects()];
    const actualActions = store.getActions();

    expect(
      actualActions.every((actualAction) =>
        expectedActions.some(
          (expectedAction) => expectedAction.type === actualAction.type
        )
      )
    );
  });

  it("can display submission errors", async () => {
    state.pod.errors = ["Oh bother..."];
    state.pod.projects = {
      "192.168.1.1": [factory.podProject()],
    };
    renderWithProviders(<AddLxd />, {
      initialEntries: ["/kvm/add"],
      state,
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });

    // Submit credentials form
    await userEvent.type(
      screen.getByRole("textbox", { name: "Name" }),
      "my-favourite-kvm"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Resource pool" }),
      "1"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Zone" }),
      "1"
    );
    await userEvent.type(
      screen.getByRole("combobox", { name: "LXD address" }),
      "192.168.1.1"
    );
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(screen.getByText("Oh bother...")).toBeInTheDocument();
  });
});
