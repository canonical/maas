import type { ReactElement } from "react";

import { Notification as NotificationBanner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import FormikForm from "@/app/base/components/FormikForm";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import urls from "@/app/networks/urls";
import type { RootState } from "@/app/store/root/types";
import { spaceActions } from "@/app/store/space";
import spaceSelectors from "@/app/store/space/selectors";
import type { Space } from "@/app/store/space/types";
import { getCanBeDeleted } from "@/app/store/space/utils";

type DeleteSpaceProps = {
  id: Space["id"];
};

export const DeleteSpace = ({ id }: DeleteSpaceProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const space = useSelector((state: RootState) =>
    spaceSelectors.getById(state, id)
  );
  const canBeDeleted = getCanBeDeleted(space);
  const dispatch = useDispatch();
  const errors = useSelector(spaceSelectors.errors);
  const saving = useSelector(spaceSelectors.saving);
  const saved = useSelector(spaceSelectors.saved);

  useFetchActions([spaceActions.fetch]);

  return (
    <FormikForm<EmptyObject>
      cleanup={spaceActions.cleanup}
      errors={errors}
      initialValues={{}}
      onCancel={closeSidePanel}
      onSubmit={() => {
        dispatch(spaceActions.cleanup());
        dispatch(spaceActions.delete(id));
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      savedRedirect={urls.spaces.index}
      saving={saving}
      submitAppearance="negative"
      submitDisabled={!canBeDeleted}
      submitLabel="Delete space"
    >
      {canBeDeleted ? (
        <NotificationBanner borderless severity="caution">
          Are you sure you want to delete this space?
        </NotificationBanner>
      ) : (
        <NotificationBanner borderless severity="negative">
          Space cannot be deleted because it has subnets attached. Remove all
          subnets from the space to allow deletion.
        </NotificationBanner>
      )}
    </FormikForm>
  );
};

export default DeleteSpace;
