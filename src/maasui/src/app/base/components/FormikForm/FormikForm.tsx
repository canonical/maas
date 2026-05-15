import { Formik } from "formik";
import type { FormikConfig } from "formik";

import FormikFormContent from "@/app/base/components/FormikFormContent";
import type { Props as ContentProps } from "@/app/base/components/FormikFormContent/FormikFormContent";

// explicitly disallow null and undefined as they cause Formik to throw an error
type InputFieldValue =
  | string[]
  | boolean
  | number
  | object
  | string
  | undefined;
export type FormikFormValues = Record<string, InputFieldValue>;

export type Props<V extends object, E = null> = ContentProps<V, E> &
  FormikConfig<V> & { initialValues: FormikFormValues };

const FormikForm = <V extends object, E = null>({
  allowAllEmpty,
  allowUnchanged,
  buttonsClassName,
  buttonsHelpClassName,
  buttonsHelp,
  cancelDisabled,
  children,
  className,
  cleanup,
  editable,
  errors,
  footer,
  inline,
  loading,
  onCancel,
  onSaveAnalytics,
  onSuccess,
  onValuesChanged,
  resetOnSave,
  saved,
  savedRedirect,
  saving,
  savingLabel,
  secondarySubmit,
  secondarySubmitSaved,
  secondarySubmitSaving,
  secondarySubmitDisabled,
  secondarySubmitLabel,
  secondarySubmitTooltip,
  submitAppearance,
  submitDisabled,
  submitLabel,
  "aria-label": ariaLabel,
  buttonsBehavior = "coupled",
  ...formikProps
}: Props<V, E>): React.ReactElement => {
  return (
    <Formik<V> {...formikProps}>
      <FormikFormContent<V, E>
        allowAllEmpty={allowAllEmpty}
        allowUnchanged={allowUnchanged}
        aria-label={ariaLabel}
        buttonsBehavior={buttonsBehavior}
        buttonsClassName={buttonsClassName}
        buttonsHelp={buttonsHelp}
        buttonsHelpClassName={buttonsHelpClassName}
        cancelDisabled={cancelDisabled}
        className={className}
        cleanup={cleanup}
        editable={editable}
        errors={errors}
        footer={footer}
        inline={inline}
        loading={loading}
        onCancel={onCancel}
        onSaveAnalytics={onSaveAnalytics}
        onSuccess={onSuccess}
        onValuesChanged={onValuesChanged}
        resetOnSave={resetOnSave}
        saved={saved}
        savedRedirect={savedRedirect}
        saving={saving}
        savingLabel={savingLabel}
        secondarySubmit={secondarySubmit}
        secondarySubmitDisabled={secondarySubmitDisabled}
        secondarySubmitLabel={secondarySubmitLabel}
        secondarySubmitSaved={secondarySubmitSaved}
        secondarySubmitSaving={secondarySubmitSaving}
        secondarySubmitTooltip={secondarySubmitTooltip}
        submitAppearance={submitAppearance}
        submitDisabled={submitDisabled}
        submitLabel={submitLabel}
      >
        {children}
      </FormikFormContent>
    </Formik>
  );
};

export default FormikForm;
