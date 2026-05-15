import type { ReactElement } from "react";

import { useDeleteSshKey } from "@/app/api/query/sshKeys";
import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type DeleteSSHKeyProps = {
  ids: number[];
};

const DeleteSSHKey = ({ ids }: DeleteSSHKeyProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const deleteSshKey = useDeleteSshKey();

  return (
    <ModelActionForm
      aria-label="Confirm SSH key deletion"
      errors={deleteSshKey.error}
      initialValues={{}}
      message={`Are you sure you want to delete ${
        ids.length > 1 ? "these SSH keys" : "this SSH key"
      }?`}
      modelType="SSH key"
      onCancel={closeSidePanel}
      onSubmit={() => {
        ids.forEach((id) => {
          deleteSshKey.mutate({ path: { id } });
        });
      }}
      onSuccess={closeSidePanel}
      saved={deleteSshKey.isSuccess}
      saving={deleteSshKey.isPending}
    />
  );
};

export default DeleteSSHKey;
