import type { ReactElement } from "react";
import { useCallback } from "react";

import { useDispatch, useSelector } from "react-redux";

import ActionForm from "@/app/base/components/ActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import { podActions } from "@/app/store/pod";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";

type Props = {
  hostIds: Pod["id"][];
};

const RefreshForm = ({ hostIds }: Props): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const errors = useSelector(podSelectors.errors);
  const refreshing = useSelector(podSelectors.refreshing);
  const cleanup = useCallback(() => podActions.cleanup(), []);

  return (
    <ActionForm<EmptyObject>
      actionName="refresh"
      cleanup={cleanup}
      errors={errors}
      initialValues={{}}
      modelName="KVM host"
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Submit",
        category: "KVM details action form",
        label: "Refresh",
      }}
      onSubmit={() => {
        hostIds.forEach((id) => {
          dispatch(podActions.refresh(id));
        });
      }}
      onSuccess={closeSidePanel}
      processingCount={refreshing.length}
      selectedCount={hostIds.length}
    >
      <p>
        Refreshing KVM hosts will cause MAAS to recalculate usage metrics,
        update information about storage pools, and commission any machines
        present in the KVM hosts that are not yet known to MAAS.
      </p>
    </ActionForm>
  );
};

export default RefreshForm;
