import { Route, Routes } from "react-router";

import DHCPSnippets from "./DHCPSnippets";

import type { Props as DHCPTableProps } from "@/app/base/components/DHCPTable/DHCPTable";
import urls from "@/app/base/urls";
import { subnetActions } from "@/app/store/subnet";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

const mockDHCPTable = vi.fn();
vi.mock("@/app/base/components/DHCPTable", () => ({
  default: (props: DHCPTableProps) => mockDHCPTable(props),
}));

afterEach(() => {
  vi.restoreAllMocks();
});

it("dispatches an action to fetch the subnets on mount", () => {
  const state = factory.rootState();
  const { store } = renderWithProviders(
    <DHCPSnippets modelName="subnet" subnetIds={[1, 2]} />,
    {
      state,
      initialEntries: [urls.networks.subnet.index({ id: 1 })],
    }
  );

  const expectedActions = [subnetActions.fetch()];
  const actualActions = store.getActions();
  expectedActions.forEach((expectedAction) => {
    expect(
      actualActions.find(
        (actualAction) => actualAction.type === expectedAction.type
      )
    ).toStrictEqual(expectedAction);
  });
});

it("selects the correct subnets to display in the table", () => {
  const subnets = [factory.subnet(), factory.subnet(), factory.subnet()];
  const state = factory.rootState({
    subnet: factory.subnetState({
      items: subnets,
      loading: false,
    }),
  });
  renderWithProviders(
    <Routes>
      <Route
        element={
          <DHCPSnippets
            modelName="subnet"
            subnetIds={[subnets[0].id, subnets[2].id]}
          />
        }
        path={urls.networks.subnet.index(null)}
      />
    </Routes>,
    {
      state,
      initialEntries: [urls.networks.subnet.index({ id: 1 })],
    }
  );
  expect(mockDHCPTable).toHaveBeenCalledWith(
    expect.objectContaining({
      subnets: [subnets[0], subnets[2]],
      modelName: "subnet",
    })
  );
});
