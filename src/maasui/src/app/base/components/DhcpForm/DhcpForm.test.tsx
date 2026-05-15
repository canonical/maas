import { Labels as FieldLabels } from "../DhcpFormFields";

import DhcpForm, { Labels } from "./DhcpForm";

import { dhcpsnippetActions } from "@/app/store/dhcpsnippet";
import dhcpsnippetSelectors from "@/app/store/dhcpsnippet/selectors";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("DhcpForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        items: [
          factory.dhcpSnippet({
            created: factory.timestamp("Thu, 15 Aug. 2019 06:21:39"),
            id: 1,
            name: "lease",
            updated: factory.timestamp("Thu, 15 Aug. 2019 06:21:39"),
            value: "lease 10",
          }),
          factory.dhcpSnippet({
            created: factory.timestamp("Thu, 15 Aug. 2019 06:21:39"),
            id: 2,
            name: "class",
            updated: factory.timestamp("Thu, 15 Aug. 2019 06:21:39"),
          }),
        ],
        loaded: true,
      }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("cleans up when unmounting", async () => {
    const {
      result: { unmount },
      store,
    } = renderWithProviders(<DhcpForm analyticsCategory="settings" />, {
      initialEntries: ["/"],
      state,
    });

    unmount();

    const expectedAction = dhcpsnippetActions.cleanup();
    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  it("can update a snippet", async () => {
    const dhcpSnippet = state.dhcpsnippet.items[0];

    const { store } = renderWithProviders(
      <DhcpForm analyticsCategory="settings" id={dhcpSnippet.id} />,
      { state }
    );

    await userEvent.clear(
      screen.getByRole("textbox", { name: FieldLabels.Name })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: FieldLabels.Name }),
      "new-lease"
    );
    await userEvent.click(screen.getByRole("button", { name: Labels.Submit }));

    const expectedAction = dhcpsnippetActions.update({
      description: dhcpSnippet.description,
      enabled: dhcpSnippet.enabled,
      id: dhcpSnippet.id,
      name: "new-lease",
      value: dhcpSnippet.value,
    });
    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  it("can create a snippet", async () => {
    const { store } = renderWithProviders(
      <DhcpForm analyticsCategory="settings" />,
      { state }
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: FieldLabels.Name }),
      "new-lease"
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: FieldLabels.Description }),
      "new-description"
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: FieldLabels.Enabled })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: FieldLabels.Value }),
      "new-value"
    );
    await userEvent.click(screen.getByRole("button", { name: Labels.Submit }));

    const expectedAction = dhcpsnippetActions.create({
      description: "new-description",
      enabled: true,
      name: "new-lease",
      value: "new-value",
    });
    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  // TODO: v2 state updates cannot be done without rerendering the component
  //  and losing internal state, re-add this test when v3 is available
  it.skip("can call the onSave on success", async () => {
    state.dhcpsnippet.saved = false;
    const onSave = vi.fn();

    const Proxy = ({ analyticsCategory }: { analyticsCategory: string }) => (
      <DhcpForm analyticsCategory={analyticsCategory} onSave={onSave} />
    );
    const { rerender } = renderWithProviders(
      <Proxy analyticsCategory="settings" />,
      { initialEntries: ["/"], state }
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: FieldLabels.Name }),
      "new-lease"
    );
    await userEvent.click(screen.getByRole("button", { name: Labels.Submit }));
    vi.spyOn(dhcpsnippetSelectors, "saved").mockReturnValue(true);
    rerender(<Proxy analyticsCategory="new-value" />);

    expect(onSave).toHaveBeenCalled();
  });

  it("does not call onSave if there is an error", async () => {
    state.dhcpsnippet.errors = "Uh oh!";
    const onSave = vi.fn();

    renderWithProviders(
      <DhcpForm analyticsCategory="settings" onSave={onSave} />,
      { state }
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: FieldLabels.Name }),
      "new-lease"
    );
    await userEvent.click(screen.getByRole("button", { name: Labels.Submit }));

    expect(onSave).not.toHaveBeenCalled();
  });

  it("fetches models when editing", () => {
    const { store } = renderWithProviders(
      <DhcpForm
        analyticsCategory="settings"
        id={state.dhcpsnippet.items[0].id}
      />,
      { state }
    );
    const actions = store.getActions();
    expect(actions.some((action) => action.type === "machine/fetch")).toBe(
      true
    );
    expect(actions.some((action) => action.type === "device/fetch")).toBe(true);
    expect(actions.some((action) => action.type === "subnet/fetch")).toBe(true);
    expect(actions.some((action) => action.type === "controller/fetch")).toBe(
      true
    );
  });

  it("shows a spinner when loading models", () => {
    state.subnet.loading = true;
    state.device.loading = true;
    state.controller.loading = true;
    state.machine.loading = true;
    state.subnet.loaded = false;
    state.device.loaded = false;
    state.controller.loaded = false;
    state.machine.loaded = false;

    state.dhcpsnippet.items[0].node = "xyz";
    renderWithProviders(
      <DhcpForm
        analyticsCategory="settings"
        id={state.dhcpsnippet.items[0].id}
      />,
      { state }
    );

    expect(
      screen.getByRole("alert", { name: Labels.LoadingData })
    ).toBeInTheDocument();
  });
});
