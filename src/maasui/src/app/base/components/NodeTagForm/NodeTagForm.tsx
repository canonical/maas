import { useEffect, useState } from "react";

import type { PropsWithSpread } from "@canonical/react-components";
import { Col, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import type { Props as FormikFormProps } from "@/app/base/components/FormikForm/FormikForm";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";
import type { CreateParams, Tag } from "@/app/store/tag/types";
import KernelOptionsField from "@/app/tags/components/KernelOptionsField";
import type { Props as KernelOptionsFieldProps } from "@/app/tags/components/KernelOptionsField/KernelOptionsField";

type Props = PropsWithSpread<
  {
    deployedMachinesCount?: number;
    generateDeployedMessage?: KernelOptionsFieldProps["generateDeployedMessage"];
    name: string | null;
    onTagCreated: (tag: Tag) => void;
  },
  Partial<FormikFormProps<CreateParams>>
>;

export enum Label {
  Comment = "Comment",
  Form = "Create tag",
  Name = "Tag name",
  Submit = "Create and add to tag changes",
}

const NodeTagFormSchema = Yup.object().shape({
  comment: Yup.string(),
  kernel_opts: Yup.string(),
  name: Yup.string().required("Name is required."),
});

export const NodeTagForm = ({
  deployedMachinesCount,
  generateDeployedMessage,
  name,
  onTagCreated,
  ...props
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const [savedName, setSavedName] = useState<Tag["name"] | null>(null);
  const saved = useSelector(tagSelectors.saved);
  const saving = useSelector(tagSelectors.saving);
  const errors = useSelector(tagSelectors.errors);
  const tag = useSelector((state: RootState) =>
    // Tag names are unique so fetch the newly created tag using the name
    // provided in this form.
    tagSelectors.getByName(state, savedName)
  );

  useEffect(() => {
    if (tag) {
      onTagCreated(tag);
    }
  }, [onTagCreated, tag]);

  return (
    <FormikForm<CreateParams>
      allowUnchanged
      aria-label={Label.Form}
      cleanup={tagActions.cleanup}
      errors={errors}
      initialValues={{
        comment: "",
        kernel_opts: "",
        name: name ?? "",
      }}
      onSubmit={(values) => {
        dispatch(tagActions.cleanup());
        dispatch(tagActions.create(values));
      }}
      onSuccess={({ name }) => {
        setSavedName(name);
      }}
      saved={saved}
      saving={saving}
      submitAppearance="neutral"
      submitLabel={Label.Submit}
      validationSchema={NodeTagFormSchema}
      {...props}
    >
      <Row className="u-no-padding">
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
          <KernelOptionsField
            deployedMachinesCount={deployedMachinesCount}
            generateDeployedMessage={generateDeployedMessage}
          />
        </Col>
      </Row>
    </FormikForm>
  );
};

export default NodeTagForm;
