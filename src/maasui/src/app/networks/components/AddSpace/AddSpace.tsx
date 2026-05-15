import type { ReactElement } from "react";

import { Col, Input, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { spaceActions } from "@/app/store/space";
import spaceSelectors from "@/app/store/space/selectors";

type AddSpaceValues = {
  name: string;
};

const AddSpace = (): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const isSaving = useSelector(spaceSelectors.saving);
  const isSaved = useSelector(spaceSelectors.saved);
  const errors = useSelector(spaceSelectors.errors);

  return (
    <FormikForm<AddSpaceValues>
      allowAllEmpty
      aria-label="Add space"
      cleanup={spaceActions.cleanup}
      errors={errors}
      initialValues={{ name: "" }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Add space",
        category: "Subnets form actions",
        label: "Add space",
      }}
      onSubmit={({ name }) => {
        dispatch(spaceActions.cleanup());
        dispatch(spaceActions.create({ name }));
      }}
      onSuccess={closeSidePanel}
      saved={isSaved}
      saving={isSaving}
      submitLabel="Save space"
    >
      <Row>
        <Col size={12}>
          <FormikField
            component={Input}
            disabled={isSaving}
            label="Name (optional)"
            name="name"
            type="text"
          />
        </Col>
      </Row>
    </FormikForm>
  );
};

export default AddSpace;
