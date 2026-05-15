import { useEffect } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import LicenseKeyFormFields from "../LicenseKeyFormFields";

import type { LicenseKeyFormValues } from "./types";

import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import settingsURLs from "@/app/settings/urls";
import { generalActions } from "@/app/store/general";
import { osInfo as osInfoSelectors } from "@/app/store/general/selectors";
import { licenseKeysActions } from "@/app/store/licensekeys";
import licenseKeysSelectors from "@/app/store/licensekeys/selectors";
import type { LicenseKeys } from "@/app/store/licensekeys/types";
import { LicenseKeysMeta } from "@/app/store/licensekeys/types";

type Props = {
  licenseKey?: LicenseKeys;
};

export enum Labels {
  Loading = "Loading...",
  FormLabel = "License Key Form",
}

const LicenseKeySchema = Yup.object().shape({
  osystem: Yup.string().required("Operating system is required"),
  distro_series: Yup.string().required("Release is required"),
  license_key: Yup.string().required("A license key is required"),
});

export const LicenseKeyForm = ({ licenseKey }: Props): React.ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();

  const saving = useSelector(licenseKeysSelectors.saving);
  const saved = useSelector(licenseKeysSelectors.saved);
  const errors = useSelector(licenseKeysSelectors.errors);
  const osInfoLoaded = useSelector(osInfoSelectors.loaded);
  const licenseKeysLoaded = useSelector(licenseKeysSelectors.loaded);
  const releases = useSelector(osInfoSelectors.getLicensedOsReleases);
  const osystems = useSelector(osInfoSelectors.getLicensedOsystems);
  const isLoaded = licenseKeysLoaded && osInfoLoaded;

  const title = licenseKey ? "Update license key" : "Add license key";

  const editing = !!licenseKey;

  useEffect(() => {
    if (!osInfoLoaded) {
      dispatch(generalActions.fetchOsInfo());
    }
    if (!licenseKeysLoaded) {
      dispatch(licenseKeysActions.fetch());
    }
  }, [dispatch, osInfoLoaded, licenseKeysLoaded]);

  return (
    <>
      {!isLoaded ? (
        <Spinner text={Labels.Loading} />
      ) : osystems.length > 0 ? (
        <FormikForm<LicenseKeyFormValues>
          aria-label={Labels.FormLabel}
          cleanup={licenseKeysActions.cleanup}
          errors={errors}
          initialValues={{
            osystem: licenseKey ? licenseKey.osystem : osystems[0][0],
            distro_series: licenseKey
              ? licenseKey.distro_series
              : releases[osystems[0][0]][0].value,
            license_key: licenseKey ? licenseKey.license_key : "",
          }}
          onCancel={closeSidePanel}
          onSaveAnalytics={{
            action: "Saved",
            category: "License keys settings",
            label: `${title} form`,
          }}
          onSubmit={(values) => {
            const params = {
              osystem: values.osystem,
              distro_series: values.distro_series,
              license_key: values.license_key,
            };
            if (editing) {
              if (licenseKey) {
                dispatch(
                  licenseKeysActions.update({
                    ...params,
                    [LicenseKeysMeta.PK]: licenseKey[LicenseKeysMeta.PK],
                  })
                );
              }
            } else {
              dispatch(licenseKeysActions.create(params));
            }
          }}
          onSuccess={closeSidePanel}
          saved={saved}
          savedRedirect={settingsURLs.licenseKeys.index}
          saving={saving}
          submitLabel={editing ? "Update license key" : "Add license key"}
          validationSchema={LicenseKeySchema}
        >
          <LicenseKeyFormFields osystems={osystems} releases={releases} />
        </FormikForm>
      ) : (
        <span>No available licensed operating systems.</span>
      )}
    </>
  );
};

export default LicenseKeyForm;
