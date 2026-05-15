import type { ReactElement } from "react";

import { useDispatch, useSelector } from "react-redux";

import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { reservedIpActions } from "@/app/store/reservedip";
import reservedIpSelectors from "@/app/store/reservedip/selectors";
import type { RootState } from "@/app/store/root/types";

type DeleteDHCPLeaseProps = {
  reservedIpId: number;
};
const DeleteDHCPLease = ({
  reservedIpId,
}: DeleteDHCPLeaseProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const errors = useSelector(reservedIpSelectors.errors);
  const saving = useSelector(reservedIpSelectors.saving);
  const saved = useSelector(reservedIpSelectors.saved);

  const reservedIp = useSelector((state: RootState) =>
    reservedIpSelectors.getById(state, reservedIpId)
  );

  return (
    <ModelActionForm
      aria-label="Delete static IP"
      cleanup={reservedIpActions.cleanup}
      errors={errors}
      initialValues={{}}
      message={`Are you sure you want to delete ${reservedIp?.ip}? This action is permanent and cannot be undone.`}
      modelType="static IP"
      onCancel={closeSidePanel}
      onSubmit={() => {
        reservedIp &&
          dispatch(
            reservedIpActions.delete({ id: reservedIp.id, ip: reservedIp.ip })
          );
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      saving={saving}
    />
  );
};

export default DeleteDHCPLease;
