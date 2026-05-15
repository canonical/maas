import type { ReactNode } from "react";

import { useDispatch, useSelector } from "react-redux";

import type { NodeActionFormProps } from "../types";

import ActionForm from "@/app/base/components/ActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import type { controllerActions } from "@/app/store/controller";
import type { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import type { NodeActions } from "@/app/store/types/node";
import { getNodeActionTitle } from "@/app/store/utils";
import { capitaliseFirst, kebabToCamelCase } from "@/app/utils";

export type FieldlessFormProps<E = null> = NodeActionFormProps<E> & {
  actions: typeof controllerActions | typeof machineActions;
  action: NodeActions;
  buttonsHelpClassName?: string;
  buttonsHelp?: ReactNode;
  cleanup: NonNullable<NodeActionFormProps<E>["cleanup"]>;
};

export const FieldlessForm = <E,>({
  action,
  actions,
  buttonsHelp,
  buttonsHelpClassName,
  cleanup,
  errors,
  modelName,
  nodes,
  processingCount,
  viewingDetails,
}: FieldlessFormProps<E>): React.ReactElement => {
  const dispatch = useDispatch();
  const currentFilters = FilterMachines.queryStringToFilters(location.search);
  const searchFilter = FilterMachines.filtersToString(currentFilters);
  const selectedMachines = useSelector(machineSelectors.selected);
  const { selectedCount } = useMachineSelectedCount(
    FilterMachines.parseFetchFilters(searchFilter)
  );
  const { dispatch: dispatchForSelectedMachines, ...actionProps } =
    useSelectedMachinesActionsDispatch({ selectedMachines, searchFilter });

  const { closeSidePanel } = useSidePanel();

  return (
    <ActionForm<EmptyObject, E>
      actionName={action}
      allowUnchanged
      buttonsHelp={buttonsHelp}
      buttonsHelpClassName={buttonsHelpClassName}
      cleanup={cleanup}
      errors={errors}
      initialValues={{}}
      modelName={modelName}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Submit",
        category: `${capitaliseFirst(modelName)} ${
          viewingDetails ? "details" : "list"
        } action form`,
        label: getNodeActionTitle(action),
      }}
      onSubmit={() => {
        dispatch(cleanup());
        const actionMethod = kebabToCamelCase(action);
        // Find the method for the function.
        const [, actionFunction] =
          Object.entries(actions).find(([key]) => key === actionMethod) || [];

        if (actionFunction) {
          if (selectedMachines) {
            dispatchForSelectedMachines(actionFunction);
          } else {
            nodes?.forEach((node) => {
              dispatch(actionFunction({ system_id: node.system_id }));
            });
          }
        }
      }}
      onSuccess={closeSidePanel}
      processingCount={processingCount}
      selectedCount={nodes ? nodes.length : (selectedCount ?? 0)}
      {...actionProps}
    />
  );
};

export default FieldlessForm;
