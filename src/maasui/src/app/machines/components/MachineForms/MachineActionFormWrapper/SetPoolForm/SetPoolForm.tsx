import { useEffect, useState } from "react";

import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import SetPoolFormFields from "./SetPoolFormFields";
import type { SetPoolFormValues } from "./types";

import { useCreatePool, usePools } from "@/app/api/query/pools";
import type { ResourcePoolResponse } from "@/app/apiclient";
import ActionForm from "@/app/base/components/ActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { APIError } from "@/app/base/types";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineEventErrors } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { NodeActions } from "@/app/store/types/node";

type Props = {
  isViewingDetails: boolean;
};

const SetPoolSchema = Yup.object().shape({
  description: Yup.string(),
  name: Yup.string().required("Resource pool required"),
  poolSelection: Yup.string().oneOf(["create", "select"]).required(),
});

export const SetPoolForm = ({
  isViewingDetails,
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const searchFilter = FilterMachines.filtersToString(
    FilterMachines.queryStringToFilters(location.search)
  );

  const selectedMachines = useSelector(machineSelectors.selected);
  const { selectedCount } = useMachineSelectedCount(
    FilterMachines.parseFetchFilters(searchFilter)
  );
  const {
    dispatch: dispatchForSelectedMachines,
    actionErrors: errors,
    ...actionProps
  } = useSelectedMachinesActionsDispatch({ selectedMachines, searchFilter });
  const [initialValues, setInitialValues] = useState<SetPoolFormValues>({
    poolSelection: "select",
    description: "",
    name: "",
  });
  const resourcePools = usePools();
  const createPool = useCreatePool();
  const errorsToShow =
    Object.keys(errors || {}).length > 0
      ? errors
      : (resourcePools.error as APIError);

  useEffect(
    () => () => {
      dispatch(machineActions.cleanup());
    },
    [dispatch]
  );

  const { closeSidePanel } = useSidePanel();

  return (
    <ActionForm<SetPoolFormValues, MachineEventErrors>
      actionName={NodeActions.SET_POOL}
      cleanup={machineActions.cleanup}
      errors={errorsToShow}
      initialValues={initialValues}
      loaded={!resourcePools.isPending}
      modelName="machine"
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Submit",
        category: `Machine ${isViewingDetails ? "details" : "list"} action form`,
        label: "Set pool",
      }}
      onSubmit={async (values) => {
        dispatch(machineActions.cleanup());
        let pool = resourcePools.data?.items.find(
          (pool) => pool.name === values.name
        ) as ResourcePoolResponse;
        if (values.poolSelection === "create") {
          pool = await createPool.mutateAsync({
            body: { name: values.name, description: values.description },
          });
        }

        if (!pool) return;

        dispatchForSelectedMachines(machineActions.setPool, {
          pool_id: pool.id,
        });

        // Store the values in case there are errors and the form needs to be
        // displayed again.
        setInitialValues(values);
      }}
      onSuccess={closeSidePanel}
      selectedCount={selectedCount ?? 0}
      validationSchema={SetPoolSchema}
      {...actionProps}
    >
      <SetPoolFormFields />
    </ActionForm>
  );
};

export default SetPoolForm;
