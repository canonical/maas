import { Labels as LicenseKeyFormLabels } from "../LicenseKeyForm/LicenseKeyForm";
import { Labels as FormFieldsLabels } from "../LicenseKeyFormFields/LicenseKeyFormFields";

import { LicenseKeyEdit, Labels as LicenseKeyLabels } from "./LicenseKeyEdit";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("LicenseKeyEdit", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        osInfo: factory.osInfoState({
          loaded: true,
          loading: false,
          data: factory.osInfo({
            osystems: [
              ["ubuntu", "Ubuntu"],
              ["windows", "Windows"],
            ],
            releases: [
              ["ubuntu/bionic", "Ubuntu 18.04 LTS 'Bionic Beaver'"],
              ["windows/win2012*", "Windows Server 2012"],
              ["windows/win2019*", "Windows Server 2019"],
            ],
          }),
        }),
      }),
      licensekeys: factory.licenseKeysState({
        errors: {},
        items: [
          factory.licenseKeys({
            osystem: "windows",
            distro_series: "win2012",
            license_key: "XXXXX-XXXXX-XXXXX-XXXXX-XXXXA",
            resource_uri: "/MAAS/api/2.0/license-key/windows/win2012",
          }),
          factory.licenseKeys({
            osystem: "windows",
            distro_series: "win2019",
            license_key: "XXXXX-XXXXX-XXXXX-XXXXX-XXXX7",
            resource_uri: "/MAAS/api/2.0/license-key/windows/win2019",
          }),
        ],
        loaded: true,
      }),
    });
  });

  it("displays a loading component if loading", () => {
    state.licensekeys.loading = true;
    state.licensekeys.loaded = false;

    renderWithProviders(
      <LicenseKeyEdit distro_series={"win2012"} osystem={"windows"} />,
      { state }
    );
    expect(screen.getByText(LicenseKeyLabels.Loading)).toBeInTheDocument();
  });

  it("handles license key not found", () => {
    renderWithProviders(
      <LicenseKeyEdit distro_series={"foo"} osystem={"bar"} />,
      { state }
    );
    expect(screen.getByText(LicenseKeyLabels.KeyNotFound)).toBeInTheDocument();
  });

  it("can display a license key edit form", () => {
    renderWithProviders(
      <LicenseKeyEdit distro_series={"win2012"} osystem={"windows"} />,
      { state }
    );

    expect(
      screen.getByRole("form", {
        name: LicenseKeyFormLabels.FormLabel,
      })
    ).toBeInTheDocument();

    const operatingSystem: HTMLOptionElement = screen.getByRole("option", {
      name: "Windows",
    });
    expect(operatingSystem.selected).toBe(true);

    const release: HTMLOptionElement = screen.getByRole("option", {
      name: "Windows Server 2012",
    });
    expect(release.selected).toBe(true);

    expect(
      screen.getByRole("textbox", { name: FormFieldsLabels.LicenseKey })
    ).toHaveValue("XXXXX-XXXXX-XXXXX-XXXXX-XXXXA");
  });
});
