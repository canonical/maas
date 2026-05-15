import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import { useQueryClient } from "@tanstack/react-query";
import * as Yup from "yup";

import { useGetGroup, useUpdateGroup } from "@/app/api/query/groups";
import type { UpdateGroupError, UserGroupRequest } from "@/app/apiclient";
import { getGroupQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type Props = {
  id: number;
};

export const Labels = {
  name: "Group name",
  description: "Description",
};

const GroupSchema = Yup.object().shape({
  name: Yup.string()
    .required(`${Labels.name} is required`)
    .matches(/^[a-zA-Z0-9 _-]+$/, "Name cannot contain special characters"),
  description: Yup.string(),
});

const EditGroup = ({ id }: Props) => {
  const { closeSidePanel } = useSidePanel();
  const group = useGetGroup({ path: { group_id: id } });
  const eTag = group.data?.headers?.get("ETag");
  const updateGroup = useUpdateGroup();
  const queryClient = useQueryClient();

  return (
    <>
      {group.isPending && <Spinner text="Loading..." />}
      {group.isError && (
        <NotificationBanner severity="negative">
          {group.error.message}
        </NotificationBanner>
      )}
      {group.isSuccess && group.data && (
        <FormikForm<UserGroupRequest, UpdateGroupError>
          aria-label="Edit group"
          errors={updateGroup.error}
          initialValues={{
            name: group.data.name,
            description: group.data.description,
          }}
          onCancel={closeSidePanel}
          onSubmit={(values) => {
            updateGroup.mutate({
              body: {
                name: values.name,
                description: values.description,
              } as UserGroupRequest,
              headers: { ETag: eTag },
              path: { group_id: id },
            });
          }}
          onSuccess={async () => {
            await queryClient.invalidateQueries({
              queryKey: getGroupQueryKey({ path: { group_id: id } }),
            });
            closeSidePanel();
          }}
          resetOnSave={true}
          saved={updateGroup.isSuccess}
          saving={updateGroup.isPending}
          submitLabel="Save group"
          validationSchema={GroupSchema}
        >
          <FormikField label={Labels.name} name="name" required type="text" />
          <FormikField
            label={Labels.description}
            name="description"
            type="text"
          />
        </FormikForm>
      )}
    </>
  );
};

export default EditGroup;
