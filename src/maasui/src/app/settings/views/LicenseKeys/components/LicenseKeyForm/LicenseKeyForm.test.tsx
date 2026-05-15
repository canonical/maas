import { Labels as FormFieldsLabels } from "../LicenseKeyFormFields/LicenseKeyFormFields";

import {
  LicenseKeyForm,
  Labels as LicenseKeyFormLabels,
} from "./LicenseKeyForm";

import settingsURLs from "@/app/settings/urls";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

describe("LicenseKeyForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
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
      }),
    });
  });

  it("can render", () => {
    renderWithProviders(<LicenseKeyForm />, { state });

    expect(
      screen.getByRole("form", { name: LicenseKeyFormLabels.FormLabel })
    ).toBeInTheDocument();
  });

  it("cleans up when unmounting", async () => {
    const {
      result: { unmount },
      store,
    } = renderWithProviders(<LicenseKeyForm />, { state });

    unmount();

    expect(
      store.getActions().some((action) => action.type === "licensekeys/cleanup")
    ).toBe(true);
  });

  it("fetches OsInfo if not loaded", () => {
    state.general.osInfo.loaded = false;

    const { store } = renderWithProviders(<LicenseKeyForm />, { state });

    expect(
      store.getActions().some((action) => action.type === "general/fetchOsInfo")
    ).toBe(true);
  });

  it("fetches license keys if not loaded", () => {
    state.licensekeys.loaded = false;

    const { store } = renderWithProviders(<LicenseKeyForm />, { state });

    expect(
      store.getActions().some((action) => action.type === "licensekeys/fetch")
    ).toBe(true);
  });

  it("redirects when the snippet is saved", () => {
    state.licensekeys.saved = true;

    const { router } = renderWithProviders(<LicenseKeyForm />, { state });
    expect(router.state.location.pathname).toEqual(
      settingsURLs.licenseKeys.index
    );
  });

  it("can add a key", async () => {
    const { store } = renderWithProviders(<LicenseKeyForm />, { state });

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: FormFieldsLabels.OperatingSystem }),
      "Windows"
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: FormFieldsLabels.Release }),
      "Windows Server 2012"
    );

    const licenseKeyInput = screen.getByRole("textbox", {
      name: FormFieldsLabels.LicenseKey,
    });
    await userEvent.clear(licenseKeyInput);
    await userEvent.type(licenseKeyInput, "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX");

    await userEvent.click(
      screen.getByRole("button", { name: "Add license key" })
    );

    expect(
      store.getActions().find((action) => action.type === "licensekeys/create")
    ).toStrictEqual({
      type: "licensekeys/create",
      payload: {
        osystem: "windows",
        distro_series: "win2012",
        license_key: "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
      },
    });
  });

  it("can update a key", async () => {
    const licenseKey = factory.licenseKeys({
      id: 1,
      osystem: "windows",
      distro_series: "win2012",
      license_key: "XXXXX-XXXXX-XXXXX-XXXXX-XXXXY",
    });
    const { store } = renderWithProviders(
      <LicenseKeyForm licenseKey={licenseKey} />,
      { state }
    );

    const licenseKeyInput = screen.getByRole("textbox", {
      name: FormFieldsLabels.LicenseKey,
    });

    // At least one field has to be updated in order for the submit button to be enabled
    await userEvent.clear(licenseKeyInput);
    await userEvent.type(licenseKeyInput, "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX");

    await userEvent.click(
      screen.getByRole("button", { name: "Update license key" })
    );

    await waitFor(() => {
      expect(
        store
          .getActions()
          .find((action) => action.type === "licensekeys/update")
      ).toStrictEqual({
        type: "licensekeys/update",
        payload: {
          id: 1,
          osystem: "windows",
          distro_series: "win2012",
          license_key: "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
        },
      });
    });
  });
});
