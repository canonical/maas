import LicenseKeyList from ".";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("LicenseKeyList", () => {
  let initialState: RootState;

  beforeEach(() => {
    initialState = factory.rootState({
      general: factory.generalState({
        osInfo: factory.osInfoState({
          loaded: true,
          data: factory.osInfo({
            osystems: [
              ["ubuntu", "Ubuntu"],
              ["windows", "Windows"],
            ],
            releases: [
              ["ubuntu/bionic", "Ubuntu 18.04 LTS 'Bionic Beaver'"],
              ["windows/win2012*", "Windows Server 2012"],
            ],
          }),
        }),
      }),
      licensekeys: factory.licenseKeysState({
        loaded: true,
        items: [factory.licenseKeys()],
      }),
    });
  });

  it("displays a message when there are no licennse keys", () => {
    const state = { ...initialState };
    state.licensekeys.items = [];

    renderWithProviders(<LicenseKeyList />, { state });
    expect(screen.getByText("No license keys available.")).toBeInTheDocument();
  });
});
