import { ZoneColumn } from "./ZoneColumn";

import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

setupMockServer(zoneResolvers.listZones.handler());

describe("ZoneColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machine({
            system_id: "abc123",
            zone: { name: "zone-north", id: 0 },
            spaces: ["management"],
            actions: [NodeActions.SET_ZONE],
          }),
        ],
      }),
    });
  });

  it("displays the zone name", () => {
    state.machine.items[0].zone.name = "zone-one";

    renderWithProviders(
      <ZoneColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { initialEntries: ["/machines"], state }
    );
    expect(screen.getByTestId("zone")).toHaveTextContent("zone-one");
  });

  it("displays single space name", () => {
    state.machine.items[0].spaces = ["space1"];

    renderWithProviders(
      <ZoneColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { initialEntries: ["/machines"], state }
    );
    expect(screen.getByTestId("spaces")).toHaveTextContent("space1");
  });

  it("displays spaces count for multiple spaces", () => {
    state.machine.items[0].spaces = ["space1", "space2"];

    renderWithProviders(
      <ZoneColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { initialEntries: ["/machines"], state }
    );
    expect(screen.getByTestId("spaces")).toHaveTextContent("2 spaces");
  });

  it("displays a sorted Tooltip for multiple spaces", async () => {
    state.machine.items[0].spaces = ["space2", "space1", "space3"];

    renderWithProviders(
      <ZoneColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { initialEntries: ["/machines"], state }
    );

    await userEvent.hover(screen.getByTestId("spaces"));
    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent(
        /space1 space2 space3/i
      );
    });
  });

  it("displays a message if the machine cannot have its zone changed", async () => {
    state.machine.items[0].actions = [];

    renderWithProviders(
      <ZoneColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { initialEntries: ["/machines"], state }
    );
    await userEvent.click(screen.getByRole("button", { name: "Change AZ:" }));

    expect(
      screen.getByRole("button", { name: "Cannot change zone of this machine" })
    ).toBeAriaDisabled();
  });

  it("can change zones", async () => {
    const { store } = renderWithProviders(
      <ZoneColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { initialEntries: ["/machines"], state }
    );
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });
    await userEvent.click(
      await screen.findByRole("button", { name: "Change AZ:" })
    );
    const changeZoneLinks = await screen.findAllByTestId("change-zone-link");
    await userEvent.click(changeZoneLinks[0]);

    expect(
      store.getActions().find((action) => action.type === "machine/setZone")
    ).toEqual({
      type: "machine/setZone",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.SET_ZONE,
          extra: {
            zone_id: 1,
          },
          system_id: "abc123",
        },
      },
    });
  });

  it("shows a spinner when changing zones", async () => {
    renderWithProviders(
      <ZoneColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { initialEntries: ["/machines"], state }
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Change AZ:" })
      ).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "Change AZ:" }));
    const changeZoneLinks = await screen.findAllByTestId("change-zone-link");
    await userEvent.click(changeZoneLinks[0]);
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("does not render table menu if onToggleMenu not provided", () => {
    renderWithProviders(<ZoneColumn systemId="abc123" />, {
      initialEntries: ["/machines"],
      state,
    });
    expect(
      screen.queryByRole("button", { name: "Change AZ:" })
    ).not.toBeInTheDocument();
  });
});
