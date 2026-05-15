import type { ReactElement } from "react";

import { useDeleteSslKey } from "@/app/api/query/sslKeys";
import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type DeleteSSLKeyProps = {
  id: number;
};

const DeleteSSLKey = ({ id }: DeleteSSLKeyProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const deleteSSLKey = useDeleteSslKey();

  return (
    <ModelActionForm
      aria-label="Confirm SSL key deletion"
      errors={deleteSSLKey.error}
      initialValues={{}}
      message="Are you sure you want to delete this SSL key?"
      modelType="SSL key"
      onCancel={closeSidePanel}
      onSubmit={() => {
        deleteSSLKey.mutate({ path: { sslkey_id: id } });
      }}
      onSuccess={closeSidePanel}
      saved={deleteSSLKey.isSuccess}
      saving={deleteSSLKey.isPending}
    />
  );
};

export default DeleteSSLKey;
