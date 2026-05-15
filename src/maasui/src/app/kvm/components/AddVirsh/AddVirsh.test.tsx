import AddVirsh from "./AddVirsh";

import { ConfigNames } from "@/app/store/config/types";
import { generalActions } from "@/app/store/general";
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

describe("AddVirsh", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [{ name: ConfigNames.MAAS_NAME, value: "MAAS" }],
      }),
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [
            factory.powerType({
              name: PodType.VIRSH,
              fields: [
                factory.powerField({ name: "power_address" }),
                factory.powerField({ name: "power_pass" }),
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

  it("fetches the necessary data on load", async () => {
    const { store } = renderWithProviders(<AddVirsh />, {
      initialEntries: ["/kvm/add"],
      state,
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });
    const expectedActions = [generalActions.fetchPowerTypes()];
    const actualActions = store.getActions();
    expectedActions.forEach((expectedAction) => {
      expect(
        actualActions.find(
          (actualAction) => actualAction.type === expectedAction.type
        )
      ).toStrictEqual(expectedAction);
    });
  });

  it("displays a spinner if data hasn't loaded yet", () => {
    state.general.powerTypes.loaded = false;
    renderWithProviders(<AddVirsh />, {
      initialEntries: ["/kvm/add"],
      state,
    });
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("displays a message if virsh is not supported", async () => {
    state.general.powerTypes.data = [];
    state.general.powerTypes.loaded = true;
    renderWithProviders(<AddVirsh />, {
      initialEntries: ["/kvm/add"],
      state,
    });
    await waitFor(() => {
      expect(poolsResolvers.listPools.resolved).toBeTruthy();
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });
    await waitFor(() => {
      expect(screen.getByTestId("virsh-unsupported")).toBeInTheDocument();
    });
  });

  it("can handle saving a virsh KVM", async () => {
    const { store } = renderWithProviders(<AddVirsh />, {
      initialEntries: ["/kvm/add"],
      state,
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });

    await waitFor(() => {
      expect(screen.queryByText(/Loading/i)).not.toBeInTheDocument();
    });
    await userEvent.type(
      await screen.findByRole("textbox", { name: /Name/i }),
      "my-favourite-kvm"
    );
    await userEvent.selectOptions(
      await screen.findByRole("combobox", { name: /Resource pool/i }),
      "1"
    );
    await userEvent.selectOptions(screen.getByLabelText(/Zone/i), "1");

    await userEvent.click(
      screen.getByRole("button", { name: /Save Virsh host/i })
    );

    expect(
      store.getActions().find((action) => action.type === "pod/create")
    ).toStrictEqual({
      type: "pod/create",
      meta: {
        method: "create",
        model: "pod",
      },
      payload: {
        params: {
          name: "my-favourite-kvm",
          pool: 1,
          power_address: "auto",
          power_pass: "auto",
          type: PodType.VIRSH,
          zone: 1,
        },
      },
    });
  });
});
