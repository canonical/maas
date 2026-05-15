import type { ReactElement } from "react";

import { useDispatch, useSelector } from "react-redux";

import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { staticRouteActions } from "@/app/store/staticroute";
import staticRouteSelectors from "@/app/store/staticroute/selectors";
import type {
  StaticRoute,
  StaticRouteMeta,
} from "@/app/store/staticroute/types";

type DeleteStaticRouteFormProps = {
  staticRouteId?: StaticRoute[StaticRouteMeta.PK];
};

const DeleteStaticRouteForm = ({
  staticRouteId,
}: DeleteStaticRouteFormProps): ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const saved = useSelector(staticRouteSelectors.saved);
  const saving = useSelector(staticRouteSelectors.saving);

  if (!staticRouteId) {
    return null;
  }
  return (
    <ModelActionForm
      aria-label="Confirm static route deletion"
      initialValues={{}}
      modelType="static route"
      onCancel={closeSidePanel}
      onSubmit={() => {
        dispatch(staticRouteActions.delete(staticRouteId));
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      saving={saving}
    />
  );
};

export default DeleteStaticRouteForm;
