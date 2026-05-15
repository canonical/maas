import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import LicenseKeyForm from "../LicenseKeyForm";

import { useFetchActions } from "@/app/base/hooks";
import { licenseKeysActions } from "@/app/store/licensekeys";
import licenseKeysSelectors from "@/app/store/licensekeys/selectors";
import type { LicenseKeys } from "@/app/store/licensekeys/types";
import type { RootState } from "@/app/store/root/types";

export enum Labels {
  Loading = "Loading...",
  KeyNotFound = "License key not found",
}

type LicenseKeyEditProps = {
  osystem?: LicenseKeys["osystem"];
  distro_series?: LicenseKeys["distro_series"];
};

export const LicenseKeyEdit = ({
  osystem,
  distro_series,
}: LicenseKeyEditProps): React.ReactElement => {
  const loading = useSelector(licenseKeysSelectors.loading);

  const licenseKey = useSelector((state: RootState) =>
    licenseKeysSelectors.getByOsystemAndDistroSeries(
      state,
      osystem,
      distro_series
    )
  );

  useFetchActions([licenseKeysActions.fetch]);

  if (loading) {
    return <Spinner text={Labels.Loading} />;
  }
  if (!licenseKey) {
    return <h4>{Labels.KeyNotFound}</h4>;
  }
  return <LicenseKeyForm licenseKey={licenseKey} />;
};

export default LicenseKeyEdit;
