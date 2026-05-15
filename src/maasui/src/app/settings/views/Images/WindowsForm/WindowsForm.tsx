import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";

const WindowsSchema = Yup.object().shape({
  windows_kms_host: Yup.string(),
});

export enum Labels {
  FormLabel = "Windows Form",
  KMSHostLabel = "Windows KMS activation host",
}

const WindowsForm = (): React.ReactElement => {
  const dispatch = useDispatch();
  const updateConfig = configActions.update;

  const saved = useSelector(configSelectors.saved);
  const saving = useSelector(configSelectors.saving);
  const errors = useSelector(configSelectors.errors);

  const windowsKmsHost = useSelector(configSelectors.windowsKmsHost);

  return (
    <FormikForm
      aria-label={Labels.FormLabel}
      cleanup={configActions.cleanup}
      errors={errors}
      initialValues={{
        windows_kms_host: windowsKmsHost ?? "",
      }}
      onSaveAnalytics={{
        action: "Saved",
        category: "Images settings",
        label: "Windows form",
      }}
      onSubmit={(values, { resetForm }) => {
        dispatch(updateConfig(values));
        resetForm({ values });
      }}
      saved={saved}
      saving={saving}
      validationSchema={WindowsSchema}
    >
      <FormikField
        help="FQDN or IP address of the host that provides the KMS Windows activation service. (Only needed for Windows deployments using KMS activation.)"
        label={Labels.KMSHostLabel}
        name="windows_kms_host"
        type="text"
      />
    </FormikForm>
  );
};

export default WindowsForm;
