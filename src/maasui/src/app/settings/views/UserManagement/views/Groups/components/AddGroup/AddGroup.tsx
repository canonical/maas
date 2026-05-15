import * as Yup from "yup";

import { useCreateGroup } from "@/app/api/query/groups";
import type { CreateGroupError, UserGroupRequest } from "@/app/apiclient";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";

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

const AddGroup = () => {
  const { closeSidePanel } = useSidePanel();
  const createGroup = useCreateGroup();

  return (
    <FormikForm<UserGroupRequest, CreateGroupError>
      aria-label="Add group"
      errors={createGroup.error}
      initialValues={{
        name: "",
        description: "",
      }}
      onCancel={closeSidePanel}
      onSubmit={(values) => {
        createGroup.mutate({
          body: {
            name: values.name,
            description: values.description,
          } as UserGroupRequest,
        });
      }}
      onSuccess={closeSidePanel}
      resetOnSave={true}
      saved={createGroup.isSuccess}
      saving={createGroup.isPending}
      submitLabel="Save group"
      validationSchema={GroupSchema}
    >
      <FormikField
        label={Labels.name}
        name="name"
        required={true}
        type="text"
      />
      <FormikField label={Labels.description} name="description" type="text" />
    </FormikForm>
  );
};

export default AddGroup;
