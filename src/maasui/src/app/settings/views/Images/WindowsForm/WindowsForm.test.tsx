import WindowsForm, { Labels as WindowsFormLabels } from "./WindowsForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("WindowsForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        loading: false,
        loaded: true,
        items: [
          {
            name: ConfigNames.WINDOWS_KMS_HOST,
            value: "127.0.0.1",
          },
        ],
      }),
    });
  });

  it("sets windows_kms_host value", () => {
    renderWithProviders(<WindowsForm />, { state });
    expect(
      screen.getByRole("textbox", { name: WindowsFormLabels.KMSHostLabel })
    ).toHaveValue("127.0.0.1");
  });
});
