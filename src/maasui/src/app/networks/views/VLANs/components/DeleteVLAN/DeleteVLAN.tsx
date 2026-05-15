import type { ReactElement } from "react";
import { useCallback } from "react";

import { Notification as NotificationBanner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import FabricLink from "@/app/base/components/FabricLink";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import urls from "@/app/networks/urls";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { RootState } from "@/app/store/root/types";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import { isId } from "@/app/utils";

type DeleteVLANProps = {
  id: number;
};

const DeleteVLAN = ({ id }: DeleteVLANProps): ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, id)
  );
  const fabric = useSelector((state: RootState) =>
    fabricSelectors.getById(state, vlan?.fabric)
  );
  const errors = useSelector(vlanSelectors.errors);
  const saved = useSelector(vlanSelectors.saved);
  const saving = useSelector(vlanSelectors.saving);
  const cleanup = useCallback(() => vlanActions.cleanup(), []);

  if (!isId(id) || !vlan || !fabric) {
    return null;
  }

  const isDefaultVLAN = vlan.id === fabric.default_vlan_id;
  return (
    <FormikForm<EmptyObject>
      cleanup={cleanup}
      errors={errors}
      initialValues={{}}
      onCancel={closeSidePanel}
      onSubmit={() => {
        dispatch(cleanup());
        dispatch(vlanActions.delete(id));
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      savedRedirect={urls.vlans.index}
      saving={saving}
      submitAppearance="negative"
      submitDisabled={isDefaultVLAN}
      submitLabel="Delete VLAN"
    >
      {isDefaultVLAN ? (
        <NotificationBanner borderless severity="negative">
          This VLAN cannot be deleted because it is the default VLAN for{" "}
          <FabricLink id={fabric.id} />.
        </NotificationBanner>
      ) : (
        <NotificationBanner borderless severity="caution">
          Are you sure you want to delete this VLAN?
        </NotificationBanner>
      )}
    </FormikForm>
  );
};

export default DeleteVLAN;
