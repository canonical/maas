import { useEffect, useState } from "react";

import { Col, NotificationSeverity, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router";
import * as Yup from "yup";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSendAnalytics } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { SyncNavigateFunction } from "@/app/base/types";
import urls from "@/app/base/urls";
import { TAG_NAME_REGEX } from "@/app/base/validation";
import { messageActions } from "@/app/store/message";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";
import type { CreateParams, Tag } from "@/app/store/tag/types";
import DefinitionField from "@/app/tags/components/DefinitionField";
import KernelOptionsField from "@/app/tags/components/KernelOptionsField";
import { NewDefinitionMessage } from "@/app/tags/constants";

export enum Label {
  Comment = "Comment",
  Name = "Tag name",
  NameValidation = "Tag names can only contain letters, numbers, dashes or underscores.",
}

const AddTagFormSchema = Yup.object().shape({
  comment: Yup.string(),
  definition: Yup.string(),
  kernel_opts: Yup.string(),
  name: Yup.string()
    .matches(TAG_NAME_REGEX, Label.NameValidation)
    .required("Name is required."),
});

export const AddTagForm = (): React.ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const navigate: SyncNavigateFunction = useNavigate();
  const [savedName, setSavedName] = useState<Tag["name"] | null>(null);
  const saved = useSelector(tagSelectors.saved);
  const saving = useSelector(tagSelectors.saving);
  const errors = useSelector(tagSelectors.errors);
  const tag = useSelector((state: RootState) =>
    // Tag names are unique so fetch the newly created tag using the name
    // provided in this form.
    tagSelectors.getByName(state, savedName)
  );
  const sendAnalytics = useSendAnalytics();

  useEffect(() => {
    if (tag) {
      navigate({ pathname: urls.tags.tag.index({ id: tag.id }) });
      if (tag.definition) {
        sendAnalytics("XPath tagging", "Valid XPath", "Save");
      } else {
        sendAnalytics("Create Tag form", "Manual tag created", "Save");
      }
    }
  }, [navigate, tag, sendAnalytics]);

  return (
    <FormikForm<CreateParams>
      aria-label="Create tag"
      cleanup={tagActions.cleanup}
      errors={errors}
      initialValues={{
        comment: "",
        definition: "",
        kernel_opts: "",
        name: "",
      }}
      onCancel={closeSidePanel}
      onSubmit={(values) => {
        dispatch(tagActions.cleanup());
        dispatch(tagActions.create(values));
      }}
      onSuccess={({ definition, name }) => {
        setSavedName(name);
        if (!!definition) {
          dispatch(
            messageActions.add(
              `Created ${name}. ${NewDefinitionMessage}`,
              NotificationSeverity.POSITIVE
            )
          );
        }
      }}
      saved={saved}
      saving={saving}
      submitLabel="Save"
      validationSchema={AddTagFormSchema}
    >
      <Row>
        <Col size={12}>
          <FormikField
            label={Label.Name}
            name="name"
            placeholder="Enter a name for the tag."
            required
            type="text"
          />
          <FormikField
            label={Label.Comment}
            name="comment"
            placeholder="Add a comment as an explanation for this tag."
            type="text"
          />
          <KernelOptionsField />
        </Col>
        <Col size={12}>
          <DefinitionField />
        </Col>
      </Row>
    </FormikForm>
  );
};

export default AddTagForm;
