import CommissioningForm from "./CommissioningForm";

import { Labels as FormikButtonLabels } from "@/app/base/components/FormikFormButtons/FormikFormButtons";
import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("CommissioningForm", () => {
  let initialState: RootState;

  beforeEach(() => {
    initialState = factory.rootState({
      config: factory.configState({
        loaded: true,
        items: [
          {
            name: ConfigNames.COMMISSIONING_DISTRO_SERIES,
            value: "bionic",
            choices: [
              ["precise", 'Ubuntu 12.04 LTS "Precise Pangolin"'],
              ["trusty", 'Ubuntu 14.04 LTS "Trusty Tahr"'],
              ["xenial", 'Ubuntu 16.04 LTS "Xenial Xerus"'],
              ["bionic", 'Ubuntu 18.04 LTS "Bionic Beaver"'],
            ],
          },
          {
            name: ConfigNames.DEFAULT_MIN_HWE_KERNEL,
            value: "ga-16.04-lowlatency",
            choices: [
              ["", "--- No minimum kernel ---"],
              ["ga-16.04-lowlatency", "xenial (ga-16.04-lowlatency)"],
              ["ga-16.04", "xenial (ga-16.04)"],
              ["hwe-16.04-lowlatency", "xenial (hwe-16.04-lowlatency)"],
              ["hwe-16.04", "xenial (hwe-16.04)"],
              ["hwe-16.04-edge", "xenial (hwe-16.04-edge)"],
              [
                "hwe-16.04-lowlatency-edge",
                "xenial (hwe-16.04-lowlatency-edge)",
              ],
            ],
          },
        ],
      }),
      general: factory.generalState({
        osInfo: factory.osInfoState({
          loading: false,
          loaded: true,
          data: factory.osInfo(),
        }),
      }),
    });
  });

  it("dispatched an action to update config on save button click", async () => {
    const state = { ...initialState };

    const { store } = renderWithProviders(<CommissioningForm />, { state });

    await userEvent.selectOptions(
      screen.getByRole("combobox", {
        name: "Default Ubuntu release used for commissioning",
      }),
      "xenial"
    );

    await userEvent.click(
      screen.getByRole("button", { name: FormikButtonLabels.Submit })
    );

    const updateConfigAction = store
      .getActions()
      .find((action) => action.type === "config/update");
    expect(updateConfigAction).toEqual({
      type: "config/update",
      payload: {
        params: { items: { commissioning_distro_series: "xenial" } },
      },
      meta: {
        model: "config",
        method: "bulk_update",
      },
    });
  });
});
