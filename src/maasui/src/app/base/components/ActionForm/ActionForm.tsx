import { useState } from "react";

import { Spinner, Strip } from "@canonical/react-components";

import type { FormikFormProps } from "@/app/base/components/FormikForm";
import FormikForm from "@/app/base/components/FormikForm";
import { useProcessing } from "@/app/base/hooks";
import type { ActionState } from "@/app/base/types";
import type { NodeActions } from "@/app/store/types/node";
import { getNodeActionLabel } from "@/app/store/utils";

const getLabel = (
  modelName: string,
  actionName: string,
  selectedCount?: number | null,
  processingCount?: number
) => {
  const processing =
    typeof processingCount === "number" && processingCount >= 0;

  // e.g. "machine"
  let modelString = modelName;
  if (processing && typeof selectedCount === "number" && selectedCount > 1) {
    // e.g.  "1 of 2 machines"
    modelString = `${
      selectedCount - (processingCount || 0)
    } of ${selectedCount} ${modelName}s`;
  } else if (typeof selectedCount === "number" && selectedCount > 1) {
    // e.g. "2 machines"
    modelString = `${selectedCount} ${modelName}s`;
  }
  return getNodeActionLabel(modelString, actionName as NodeActions, processing);
};

export type ActionFormProps<V extends object, E = null> = Omit<
  FormikFormProps<V, E>,
  "saved" | "saving" | "savingLabel" | "submitLabel"
> & {
  actionName: string;
  loaded?: boolean;
  modelName: string;
  processingCount?: number;
  selectedCount?: number | null;
  showProcessingCount?: boolean;
  submitLabel?: string;
  actionStatus?: ActionState["status"];
  actionErrors?: ActionState["errors"];
};

export enum Labels {
  LoadingForm = "Loading form",
}

const ActionForm = <V extends object, E = null>({
  actionErrors,
  actionName,
  children,
  errors,
  loaded = true,
  modelName,
  onSubmit,
  processingCount,
  selectedCount,
  showProcessingCount = true,
  submitLabel,
  actionStatus,
  ...formikFormProps
}: ActionFormProps<V, E>): React.ReactElement | null => {
  const [selectedOnSubmit, setSelectedOnSubmit] = useState(selectedCount);
  const processingComplete = useProcessing({
    hasErrors: !!errors,
    processingCount,
  });

  if (!loaded) {
    return (
      <Strip>
        <Spinner aria-label={Labels.LoadingForm} text="Loading..." />
      </Strip>
    );
  }
  // TODO: remove processingComplete once actionStatus has been implemented across all forms
  // https://warthogs.atlassian.net/browse/MAASENG-2312
  const statusProps = {
    saving:
      actionStatus === "loading" || (!!processingCount && processingCount > 0),
    saved: actionStatus === "success" || processingComplete,
    errors: errors || actionErrors,
  };

  return (
    <FormikForm<V, E>
      onSubmit={(values, formikHelpers) => {
        // Set selected count in component state once form is submitted, so
        // that the saving label is not affected by updates to the component's
        // selectedCount prop, e.g. unselecting or deleting items.
        setSelectedOnSubmit(selectedCount);
        return onSubmit(values, formikHelpers);
      }}
      savingLabel={
        showProcessingCount
          ? `${getLabel(
              modelName,
              actionName,
              selectedOnSubmit,
              processingCount
            )}...`
          : null
      }
      submitDisabled={selectedCount === 0}
      submitLabel={
        submitLabel ?? getLabel(modelName, actionName, selectedCount)
      }
      {...statusProps}
      {...formikFormProps}
    >
      {children}
    </FormikForm>
  );
};

export default ActionForm;
