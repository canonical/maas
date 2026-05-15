import { screen } from "@testing-library/react";

import PoolColumn from "./PoolColumn";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import { renderWithProviders, setupMockServer, waitFor } from "@/testing/utils";

setupMockServer(
  poolsResolvers.getPool.handler(),
  zoneResolvers.getZone.handler()
);

describe("PoolColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      pod: factory.podState({
        items: [
          factory.pod({
            name: "1",
            pool: 1,
            zone: 1,
          }),
        ],
      }),
    });
  });

  it("can display the pod's resource pool and zone", async () => {
    renderWithProviders(
      <PoolColumn
        poolId={state.pod.items[0].pool}
        zoneId={state.pod.items[0].zone}
      />,
      { state }
    );
    await waitFor(() => {
      expect(screen.getByTestId("pool")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByTestId("pool")).toHaveTextContent("swimming");
    });
    await waitFor(() => {
      expect(screen.getByTestId("zone")).toHaveTextContent("zone-1");
    });
  });
});
