import type { ReactElement } from "react";

import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import { useQueryClient } from "@tanstack/react-query";
import * as Yup from "yup";

import { useGetPool, useUpdatePool } from "@/app/api/query/pools";
import type {
  ResourcePoolRequest,
  UpdateResourcePoolError,
} from "@/app/apiclient";
import { getResourcePoolQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type EditPoolProps = {
  id: number;
};

const PoolSchema = Yup.object().shape({
  name: Yup.string().required("name is required"),
  description: Yup.string(),
});

const EditPool = ({ id }: EditPoolProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const queryClient = useQueryClient();
  const pool = useGetPool({ path: { resource_pool_id: id } });

  const eTag = pool.data?.headers?.get("ETag");
  const editPool = useUpdatePool();

  return (
    <>
      {pool.isPending && <Spinner text="Loading..." />}
      {pool.isError && (
        <NotificationBanner severity="negative">
          {pool.error.message}
        </NotificationBanner>
      )}
      {pool.isSuccess && pool.data && (
        <FormikForm<ResourcePoolRequest, UpdateResourcePoolError>
          aria-label="Edit pool"
          errors={editPool.error}
          initialValues={{
            description: pool.data.description,
            name: pool.data.name,
          }}
          onCancel={closeSidePanel}
          onSubmit={(values) => {
            editPool.mutate({
              headers: {
                ETag: eTag,
              },
              body: {
                name: values.name,
                description: values.description,
              },
              path: { resource_pool_id: id },
            });
          }}
          onSuccess={() => {
            return queryClient
              .invalidateQueries({
                queryKey: getResourcePoolQueryKey({
                  path: { resource_pool_id: id },
                }),
              })
              .then(closeSidePanel);
          }}
          saved={editPool.isSuccess}
          saving={editPool.isPending}
          submitLabel="Save pool"
          validationSchema={PoolSchema}
        >
          <FormikField label="Name (required)" name="name" type="text" />
          <FormikField label="Description" name="description" type="text" />
        </FormikForm>
      )}
    </>
  );
};

export default EditPool;
