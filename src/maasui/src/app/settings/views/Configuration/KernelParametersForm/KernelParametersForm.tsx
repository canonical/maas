import { ExternalLink } from "@canonical/maas-react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import TooltipButton from "@/app/base/components/TooltipButton";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";

type KernelParametersValues = {
  kernel_opts: string;
  enable_kernel_crash_dump: boolean;
};

export enum Labels {
  FormLabel = "Configuration - Kernel parameters",
  GlobalBootParams = "Global boot parameters always passed to the kernel",
  KernelCrashDump = "Try to enable kernel crash dump by default",
}

const KernelParametersSchema = Yup.object()
  .shape({
    kernel_opts: Yup.string(),
  })
  .defined();

const KernelParametersForm = (): React.ReactElement => {
  const dispatch = useDispatch();
  const updateConfig = configActions.update;

  const saved = useSelector(configSelectors.saved);
  const saving = useSelector(configSelectors.saving);
  const errors = useSelector(configSelectors.errors);

  const kernelParams = useSelector(configSelectors.kernelParams);
  const enableKernelCrashDump = useSelector(
    configSelectors.enableKernelCrashDump
  );

  return (
    <FormikForm<KernelParametersValues>
      aria-label={Labels.FormLabel}
      cleanup={configActions.cleanup}
      errors={errors}
      initialValues={{
        kernel_opts: kernelParams || "",
        enable_kernel_crash_dump: enableKernelCrashDump || false,
      }}
      onSaveAnalytics={{
        action: "Saved",
        category: "Configuration settings",
        label: "Kernel parameters form",
      }}
      onSubmit={(values, { resetForm }) => {
        dispatch(
          updateConfig({
            kernel_opts: values.kernel_opts,
            enable_kernel_crash_dump: values.enable_kernel_crash_dump,
          })
        );
        resetForm({ values });
      }}
      saved={saved}
      saving={saving}
      validationSchema={KernelParametersSchema}
    >
      <span className="p-heading--5">General</span>
      <FormikField
        label={Labels.GlobalBootParams}
        name="kernel_opts"
        type="text"
      />
      <span className="p-heading--5">Kernel crash dump</span>
      <FormikField
        help={
          <>
            To enable kernel crash dump, the hardware{" "}
            <TooltipButton
              iconName="help-mid-dark"
              message={
                <span className="u-align-text--center u-flex--center">
                  {" "}
                  &gt;= 4 CPU threads, <br /> &gt;= 6GB RAM, <br />
                  Reserve &gt;5x RAM size as free disk space in /var.
                </span>
              }
            />{" "}
            must meet the minimum requirements and the OS{" "}
            <TooltipButton
              iconName="help-mid-dark"
              message="Tested with Ubuntu 24.04 LTS or higher."
            />{" "}
            must support it. Check crash dump status in machine details.{" "}
            <ExternalLink to="https://ubuntu.com/server/docs/kernel-crash-dump">
              More about kernel crash dump
            </ExternalLink>
          </>
        }
        label={Labels.KernelCrashDump}
        name="enable_kernel_crash_dump"
        type="checkbox"
      />
    </FormikForm>
  );
};

export default KernelParametersForm;
