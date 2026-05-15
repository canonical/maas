import SubnetsList from "./SubnetsList";

import urls from "@/app/networks/urls";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

describe("SubnetsList", () => {
  const state = factory.rootState({
    fabric: factory.fabricState({
      loaded: true,
    }),
    vlan: factory.vlanState({ loaded: true }),
    subnet: factory.subnetState({ loaded: true }),
    space: factory.spaceState({ loaded: true }),
  });

  it("displays loading text", async () => {
    state.fabric.loaded = false;
    renderWithProviders(<SubnetsList />, {
      state,
    });

    expect(screen.getAllByRole("grid")).toHaveLength(1);
    await userEvent.type(screen.getByRole("searchbox"), "non-existent-fabric");
    await waitFor(() => {
      expect(screen.getByText(/Loading.../)).toBeInTheDocument();
    });
    state.fabric.loaded = true;
  });

  it("displays correct text when there are no results for the search criteria", async () => {
    renderWithProviders(<SubnetsList />, {
      state,
    });

    expect(screen.getAllByRole("grid")).toHaveLength(1);

    await userEvent.type(screen.getByRole("searchbox"), "non-existent-fabric");

    await waitFor(() => {
      expect(
        within(screen.getByRole("grid")).getByText(/No results/)
      ).toBeInTheDocument();
    });
  });

  it("sets the options from the URL on load", async () => {
    renderWithProviders(<SubnetsList />, {
      state,
      initialEntries: [
        urls.subnets.indexWithParams({ by: "space", q: "fabric-1" }),
      ],
    });

    await waitFor(() => {
      expect(
        screen.getByRole("combobox", {
          name: /group by/i,
        })
      ).toHaveValue("space");
    });

    await waitFor(() => {
      expect(screen.getByRole<HTMLInputElement>("searchbox").value).toBe(
        "fabric-1"
      );
    });
  });

  it("updates the URL on search", async () => {
    const { router } = renderWithProviders(<SubnetsList />, {
      state,
    });

    expect(new URLSearchParams(router.state.location.search).get("q")).toEqual(
      ""
    );

    await userEvent.type(screen.getByRole("searchbox"), "test-fabric");

    await waitFor(() => {
      expect(
        new URLSearchParams(router.state.location.search).get("q")
      ).toEqual("test-fabric");
    });
  });

  it("updates the URL 'by' param once a new group by option is selected", async () => {
    const { router } = renderWithProviders(<SubnetsList />, {
      state,
    });

    expect(new URLSearchParams(router.state.location.search).get("by")).toEqual(
      "fabric"
    );

    const selectBox = screen.getByRole("combobox", {
      name: /group by/i,
    });

    await userEvent.selectOptions(selectBox, "space");

    await waitFor(() => {
      expect(
        new URLSearchParams(router.state.location.search).get("by")
      ).toEqual("space");
    });
  });
});
