import type { ReactElement } from "react";

import { Notification as NotificationBanner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import FormikForm from "@/app/base/components/FormikForm";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import subnetURLs from "@/app/networks/urls";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import { getHasIPAddresses } from "@/app/store/subnet/utils";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";

type DeleteSubnetProps = {
  subnet: Subnet;
};

export const DeleteSubnet = ({
  subnet,
}: DeleteSubnetProps): ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const errors = useSelector(subnetSelectors.errors);
  const saving = useSelector(subnetSelectors.saving);
  const saved = useSelector(subnetSelectors.saved);
  const vlanOnSubnet = useSelector((state: RootState) =>
    vlanSelectors.getById(state, subnet?.vlan)
  );
  const isDHCPEnabled = vlanOnSubnet?.dhcp_on || false;
  const canBeDeleted =
    !isDHCPEnabled || (isDHCPEnabled && !getHasIPAddresses(subnet));

  useFetchActions([vlanActions.fetch, subnetActions.fetch]);

  return (
    <FormikForm<EmptyObject>
      aria-label="Delete subnet"
      cleanup={subnetActions.cleanup}
      errors={errors}
      initialValues={{}}
      onCancel={closeSidePanel}
      onSubmit={() => {
        dispatch(subnetActions.delete(subnet.id));
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      savedRedirect={subnetURLs.index}
      saving={saving}
      submitAppearance="negative"
      submitDisabled={!canBeDeleted}
      submitLabel="Delete"
    >
      {canBeDeleted ? (
        <NotificationBanner borderless severity="caution">
          Are you sure you want to delete this subnet?
          {isDHCPEnabled ? null : (
            <>
              <br />
              Beware IP addresses on devices on this subnet might not be
              retained.
            </>
          )}
        </NotificationBanner>
      ) : (
        <NotificationBanner borderless severity="negative">
          This subnet cannot be deleted as there are nodes that have an IP
          address obtained through DHCP services on this subnet. Release these
          nodes in order to proceed.
        </NotificationBanner>
      )}
    </FormikForm>
  );
};

export default DeleteSubnet;
