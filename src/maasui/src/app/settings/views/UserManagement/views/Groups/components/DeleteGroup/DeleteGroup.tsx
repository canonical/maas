import {
  Spinner,
  Notification as NotificationBanner,
} from "@canonical/react-components";
import pluralize from "pluralize";

import { useDeleteGroup, useGetGroup } from "@/app/api/query/groups";
import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type Props = {
  id: number;
  user_count: number;
};

const DeleteGroup = ({ id, user_count }: Props) => {
  const { closeSidePanel } = useSidePanel();
  const deleteGroup = useDeleteGroup();
  const group = useGetGroup({ path: { group_id: id } });
  const eTag = group.data?.headers?.get("ETag");
  return (
    <>
      {group.isPending && <Spinner text="Loading..." />}
      {group.isError && (
        <NotificationBanner severity="negative">
          {group.error.message}
        </NotificationBanner>
      )}
      <ModelActionForm
        aria-label="Delete group"
        errors={deleteGroup.error}
        initialValues={{}}
        message={
          user_count ? (
            <NotificationBanner
              severity="caution"
              title="Are you sure you want to delete this group?"
            >
              This action will remove permissions for{" "}
              <b>
                {user_count} associated {pluralize("member", user_count)}
              </b>{" "}
              and can not be undone.
            </NotificationBanner>
          ) : null
        }
        modelType="group"
        onCancel={closeSidePanel}
        onSubmit={() => {
          deleteGroup.mutate({
            path: { group_id: id },
            headers: { ETag: eTag },
          });
        }}
        onSuccess={closeSidePanel}
        saved={deleteGroup.isSuccess}
        saving={deleteGroup.isPending}
        submitAppearance="negative"
      />
    </>
  );
};

export default DeleteGroup;
