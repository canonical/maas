import type { ReactElement } from "react";

import { Col, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { spaceActions } from "@/app/store/space";
import spaceSelectors from "@/app/store/space/selectors";
import type { Space } from "@/app/store/space/types";

export type SpaceSummaryValues = Pick<Space, "description" | "name">;
const spaceSummaryFormSchema = Yup.object().shape({
  name: Yup.string(),
  description: Yup.string(),
});

const EditSpace = ({
  space,
  handleDismiss,
}: {
  space: Space;
  handleDismiss: () => void;
}): ReactElement => {
  const spaceErrors = useSelector(spaceSelectors.errors);
  const saving = useSelector(spaceSelectors.saving);
  const saved = useSelector(spaceSelectors.saved);
  const dispatch = useDispatch();

  return (
    <FormikForm<SpaceSummaryValues>
      aria-label="Edit space summary"
      cleanup={spaceActions.cleanup}
      errors={spaceErrors}
      initialValues={{
        name: space.name,
        description: space.description,
      }}
      onCancel={handleDismiss}
      onSaveAnalytics={{
        action: "Save",
        category: "Space",
        label: "Space summary form",
      }}
      onSubmit={({ name, description }) => {
        dispatch(spaceActions.update({ id: space.id, name, description }));
      }}
      onSuccess={() => {
        handleDismiss();
      }}
      resetOnSave
      saved={saved}
      saving={saving}
      submitLabel="Save"
      validationSchema={spaceSummaryFormSchema}
    >
      <Row>
        <Col size={6}>
          <FormikField label="Name" name="name" type="text" />
          <FormikField label="Description" name="description" type="text" />
        </Col>
      </Row>
    </FormikForm>
  );
};

export default EditSpace;
