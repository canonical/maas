import DeviceName from "./DeviceName";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("DeviceName", () => {
  let state: RootState;
  const domain = factory.domain({ id: 99 });
  beforeEach(() => {
    state = factory.rootState({
      domain: factory.domainState({
        loaded: true,
        items: [domain],
      }),
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [factory.powerType()],
        }),
      }),
      device: factory.deviceState({
        loaded: true,
        items: [
          factory.deviceDetails({
            domain,
            locked: false,
            permissions: ["edit"],
            system_id: "abc123",
          }),
        ],
      }),
    });
  });

  it("can update a device with the new name and domain", async () => {
    const { store } = renderWithProviders(
      <DeviceName editingName={true} id="abc123" setEditingName={vi.fn()} />,
      { initialEntries: ["/device/abc123"], state }
    );

    await userEvent.clear(screen.getByRole("textbox", { name: "Hostname" }));

    await userEvent.type(
      screen.getByRole("textbox", { name: "Hostname" }),
      "new-lease"
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Domain" }),
      "99"
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(
      store.getActions().find((action) => action.type === "device/update")
    ).toStrictEqual({
      type: "device/update",
      payload: {
        params: {
          domain: domain,
          hostname: "new-lease",
          system_id: "abc123",
        },
      },
      meta: {
        model: "device",
        method: "update",
      },
    });
  });
});
