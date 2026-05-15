import AddVirsh from "../AddVirsh";

import { ConfigNames } from "@/app/store/config/types";
import { PowerTypeNames } from "@/app/store/general/constants";
import { PowerFieldScope } from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  poolsResolvers.listPools.handler(),
  zoneResolvers.listZones.handler()
);

describe("AddVirshFields", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [{ name: ConfigNames.MAAS_NAME, value: "MAAS" }],
      }),
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [],
          loaded: true,
        }),
      }),
      pod: factory.podState({
        items: [],
        loaded: true,
        loading: false,
        saved: false,
        saving: false,
      }),
    });
  });

  it("does not show power type fields that are scoped to nodes", async () => {
    state.general.powerTypes.data = [
      factory.powerType({
        description: "Virsh (virtual systems)",
        fields: [
          factory.powerField({
            name: "field1",
            scope: PowerFieldScope.BMC,
            label: "test-powerfield-label-1",
          }),
          factory.powerField({
            name: "field2",
            scope: PowerFieldScope.NODE,
            label: "test-powerfield-label-2",
          }),
        ],
        name: PowerTypeNames.VIRSH,
      }),
    ];

    renderWithProviders(<AddVirsh />, {
      state,
      initialEntries: ["/machines/chassis/add"],
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });

    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: /test-powerfield-label-1/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("textbox", { name: /test-powerfield-label-2/i })
    ).not.toBeInTheDocument();
  });
});
