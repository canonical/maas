import * as Yup from "yup";

import { useCreateRack } from "@/app/api/query/racks";
import type { CreateRackError, RackRequest } from "@/app/apiclient";
import FormikField from "@/app/base/components/FormikField/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";

const RackSchema = Yup.object().shape({
  name: Yup.string().required("'Name' is a required field."),
});

const AddRack = () => {
  const { closeSidePanel } = useSidePanel();
  const createRack = useCreateRack();

  return (
    <FormikForm<RackRequest, CreateRackError>
      aria-label="Add rack"
      errors={createRack.error}
      initialValues={{
        name: "",
      }}
      onCancel={closeSidePanel}
      onSubmit={(values) => {
        createRack.mutate({
          body: {
            name: values.name,
          },
        });
      }}
      onSuccess={() => {
        closeSidePanel();
      }}
      resetOnSave={true}
      saved={createRack.isSuccess}
      saving={createRack.isPending}
      submitLabel="Save rack"
      validationSchema={RackSchema}
    >
      <FormikField label="* Name" name="name" type="text" />
    </FormikForm>
  );
};

export default AddRack;
