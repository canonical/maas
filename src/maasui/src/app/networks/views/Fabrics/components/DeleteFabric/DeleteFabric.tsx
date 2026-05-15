import type { ReactElement, ReactNode } from "react";
import { useCallback } from "react";

import { Notification as NotificationBanner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import FormikForm from "@/app/base/components/FormikForm";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import urls from "@/app/networks/urls";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { Fabric, FabricMeta } from "@/app/store/fabric/types";
import type { RootState } from "@/app/store/root/types";
import subnetSelectors from "@/app/store/subnet/selectors";
import { isId } from "@/app/utils";

type DeleteFabricProps = {
  id?: Fabric[FabricMeta.PK] | null;
};

const DeleteFabric = ({ id }: DeleteFabricProps): ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const fabric = useSelector((state: RootState) =>
    fabricSelectors.getById(state, id)
  );
  const subnetsInFabric = useSelector((state: RootState) =>
    subnetSelectors.getByFabric(state, id)
  );
  const errors = useSelector(fabricSelectors.errors);
  const saved = useSelector(fabricSelectors.saved);
  const saving = useSelector(fabricSelectors.saving);
  const cleanup = useCallback(() => fabricActions.cleanup(), []);

  useFetchActions([fabricActions.fetch]);

  // TODO: better error handling
  if (!isId(id) || !fabric) {
    return null;
  }

  const fabricIsDefault = fabric.id === 0;
  const hasSubnets = subnetsInFabric.length > 0;
  let warning: ReactNode;
  if (fabricIsDefault) {
    warning = (
      <NotificationBanner borderless severity="negative">
        This fabric cannot be deleted because it is the default fabric for this
        MAAS.
      </NotificationBanner>
    );
  } else if (hasSubnets) {
    warning = (
      <NotificationBanner borderless severity="negative">
        This fabric cannot be deleted because it has subnets attached. Remove
        all subnets from the VLANs on this fabric to allow deletion.
      </NotificationBanner>
    );
  } else {
    warning = (
      <NotificationBanner borderless severity="caution">
        Are you sure you want to delete this fabric?
      </NotificationBanner>
    );
  }
  return (
    <FormikForm<EmptyObject>
      cleanup={cleanup}
      errors={errors}
      initialValues={{}}
      onCancel={closeSidePanel}
      onSubmit={() => {
        dispatch(cleanup());
        dispatch(fabricActions.delete(id));
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      savedRedirect={urls.fabrics.index}
      saving={saving}
      submitAppearance="negative"
      submitDisabled={fabricIsDefault || hasSubnets}
      submitLabel="Delete fabric"
    >
      {warning}
    </FormikForm>
  );
};

export default DeleteFabric;
