import type { ReactElement } from "react";

import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import { useQueryClient } from "@tanstack/react-query";

import { useDeleteUser, useGetUser } from "@/app/api/query/users";
import { getUserQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";
import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type DeleteUserProps = {
  id: number;
};

const DeleteUser = ({ id }: DeleteUserProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const queryClient = useQueryClient();
  const user = useGetUser({ path: { user_id: id } });
  const eTag = user.data?.headers?.get("ETag");
  const deleteUser = useDeleteUser();

  return (
    <>
      {user.isPending && <Spinner text="Loading..." />}
      {user.isError && (
        <NotificationBanner severity="negative">
          {user.error.message}
        </NotificationBanner>
      )}
      {user.isSuccess && user.data && (
        <ModelActionForm
          aria-label="Confirm user deletion"
          errors={deleteUser.error}
          initialValues={{}}
          message={
            <>
              {`Are you sure you want to delete \`${user.data.username}\`?`}
              <br />
              <span className="u-text--light">
                This action is permanent and can not be undone.
              </span>
            </>
          }
          modelType="user"
          onCancel={closeSidePanel}
          onSubmit={() => {
            deleteUser.mutate({
              headers: { ETag: eTag },
              path: { user_id: id },
            });
          }}
          onSuccess={async () => {
            // async with closeForm called first, because unlike
            // other delete forms, this one uses GET
            closeSidePanel();
            return queryClient.invalidateQueries({
              queryKey: getUserQueryKey({
                path: { user_id: id },
              }),
            });
          }}
          saved={deleteUser.isSuccess}
          saving={deleteUser.isPending}
        />
      )}
    </>
  );
};

export default DeleteUser;
