import { Formik } from "formik";

import LicenseKeyFormFields, {
  Labels as FormFieldsLabels,
} from "./LicenseKeyFormFields";

import type { OSInfoOptions } from "@/app/store/general/selectors/osInfo";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("LicenseKeyFormFields", () => {
  let state: RootState;
  let osystems: string[][];
  let releases: OSInfoOptions;

  beforeEach(() => {
    osystems = [["windows", "Windows"]];
    releases = {
      windows: [{ value: "win2012", label: "Windows Server 2012" }],
    };
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
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <LicenseKeyFormFields osystems={osystems} releases={releases} />
      </Formik>,
      { state }
    );

    expect(
      screen.getByRole("combobox", {
        name: FormFieldsLabels.OperatingSystem,
      })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("combobox", {
        name: FormFieldsLabels.Release,
      })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("textbox", {
        name: FormFieldsLabels.LicenseKey,
      })
    ).toBeInTheDocument();
  });
});
