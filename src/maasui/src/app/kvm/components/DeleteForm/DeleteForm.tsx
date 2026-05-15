import { useCallback } from "react";

import { Col, Icon, NotificationSeverity } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router";
import * as Yup from "yup";

import ActionForm from "@/app/base/components/ActionForm";
import FormikField from "@/app/base/components/FormikField";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { SyncNavigateFunction } from "@/app/base/types";
import urls from "@/app/base/urls";
import { machineActions } from "@/app/store/machine";
import { messageActions } from "@/app/store/message";
import { podActions } from "@/app/store/pod";
import { PodType } from "@/app/store/pod/constants";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod, PodMeta } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import { vmClusterActions } from "@/app/store/vmcluster";
import vmClusterSelectors from "@/app/store/vmcluster/selectors";
import type { VMCluster, VMClusterMeta } from "@/app/store/vmcluster/types";

type DeleteFormValues = {
  decompose: boolean;
};

type Props = {
  clusterId?: VMCluster[VMClusterMeta.PK] | null;
  hostId?: Pod[PodMeta.PK] | null;
};

const DeleteFormSchema = Yup.object().shape({
  decompose: Yup.boolean(),
});

const DeleteForm = ({
  clusterId,
  hostId,
}: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const navigate: SyncNavigateFunction = useNavigate();
  const { closeSidePanel } = useSidePanel();
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  );
  const cluster = useSelector((state: RootState) =>
    vmClusterSelectors.getById(state, clusterId)
  );
  const podErrors = useSelector(podSelectors.errors);
  const vmClusterErrors = useSelector((state: RootState) =>
    vmClusterSelectors.eventError(state, "delete")
  );
  const podsDeleting = useSelector(podSelectors.deleting);
  const clusterDeleting = useSelector((state: RootState) =>
    vmClusterSelectors.status(state, "deleting")
  );
  const cleanup = useCallback(() => {
    dispatch(vmClusterActions.cleanup());
    return podActions.cleanup();
  }, [dispatch]);
  const vmClusterError = vmClusterErrors?.length
    ? vmClusterErrors[0]?.error
    : null;
  const errors = podErrors || vmClusterError;
  const showRemoveMessage = (pod && pod.type === PodType.LXD) || cluster;
  const clusterDeletingCount = clusterDeleting ? 1 : 0;
  const deletingCount = pod ? podsDeleting.length : clusterDeletingCount;

  if (!pod && !cluster) {
    return null;
  }

  return (
    <ActionForm<DeleteFormValues>
      actionName="remove"
      allowAllEmpty
      allowUnchanged
      cleanup={cleanup}
      errors={errors}
      initialValues={{
        decompose: false,
      }}
      modelName={pod ? "KVM host" : "cluster"}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Submit",
        category: "KVM details action form",
        label: `Remove ${pod ? "KVM host" : "cluster"}`,
      }}
      onSubmit={(values: DeleteFormValues) => {
        // Clean up so that previous errors are cleared.
        dispatch(cleanup());
        if (pod) {
          dispatch(
            podActions.delete({
              decompose: values.decompose,
              id: pod.id,
            })
          );
        } else if (cluster) {
          dispatch(
            vmClusterActions.delete({
              decompose: values.decompose,
              id: cluster.id,
            })
          );
        }
      }}
      onSuccess={() => {
        dispatch(
          messageActions.add(
            `${pod ? "KVM host" : "Cluster"} removed successfully`,
            NotificationSeverity.INFORMATION
          )
        );
        navigate({ pathname: urls.kvm.index });
        closeSidePanel();
        dispatch(machineActions.invalidateQueries());
      }}
      processingCount={deletingCount}
      submitAppearance="negative"
      validationSchema={DeleteFormSchema}
    >
      {showRemoveMessage && (
        <Col size={6}>
          <p>
            <Icon className="is-inline" name="warning" />
            Once a {pod ? "KVM host" : "cluster"} is removed, you can still
            access all VMs in this {pod ? "project" : "cluster"} from the LXD
            server.
          </p>
          <FormikField
            label={
              <>
                Selecting this option will delete all VMs in{" "}
                <strong>{pod?.name || cluster?.name}</strong> along with their
                storage.
              </>
            }
            name="decompose"
            type="checkbox"
            wrapperClassName="u-nudge-right--large"
          />
        </Col>
      )}
    </ActionForm>
  );
};

export default DeleteForm;
