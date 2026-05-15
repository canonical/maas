import { useDispatch, useSelector } from "react-redux";

import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { licenseKeysActions } from "@/app/store/licensekeys";
import licenseKeysSelectors from "@/app/store/licensekeys/selectors";
import type { LicenseKeys } from "@/app/store/licensekeys/types";

type Props = {
  licenseKey: LicenseKeys;
};

const LicenseKeyDelete = ({ licenseKey }: Props) => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const errors = useSelector(licenseKeysSelectors.errors);
  const saved = useSelector(licenseKeysSelectors.saved);
  const saving = useSelector(licenseKeysSelectors.saving);

  return (
    <ModelActionForm
      aria-label="Confirm license key deletion"
      errors={errors}
      initialValues={{}}
      modelType="license key"
      onCancel={closeSidePanel}
      onSubmit={() => {
        dispatch(licenseKeysActions.delete(licenseKey));
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      saving={saving}
    />
  );
};

export default LicenseKeyDelete;
