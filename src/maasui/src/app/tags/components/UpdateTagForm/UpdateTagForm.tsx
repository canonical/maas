import { NotificationSeverity, Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import UpdateTagFormFields from "./UpdateTagFormFields";

import FormikForm from "@/app/base/components/FormikForm";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { messageActions } from "@/app/store/message";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag, TagMeta, UpdateParams } from "@/app/store/tag/types";
import { NewDefinitionMessage } from "@/app/tags/constants";

type Props = {
  id: Tag[TagMeta.PK];
};

export enum Label {
  Form = "Update tag",
}

const UpdateTagFormSchema = Yup.object().shape({
  comment: Yup.string(),
  kernel_opts: Yup.string(),
  name: Yup.string().required("Name is required."),
});

const UpdateAutoTagFormSchema = Yup.object().shape({
  comment: Yup.string(),
  definition: Yup.string().required(
    "Removing the definition of automatic tags is not allowed. Please, consider creating a new tag."
  ),
  kernel_opts: Yup.string(),
  name: Yup.string().required("Name is required."),
});

const UpdateTagForm = ({ id }: Props): React.ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const tag = useSelector((state: RootState) =>
    tagSelectors.getById(state, id)
  );
  const saved = useSelector(tagSelectors.saved);
  const saving = useSelector(tagSelectors.saving);
  const errors = useSelector(tagSelectors.errors);

  useFetchActions([tagActions.fetch]);

  if (!tag) {
    return <Spinner data-testid="Spinner" />;
  }

  const isAuto = !!tag.definition;

  return (
    <FormikForm<UpdateParams>
      aria-label="Update tag"
      cleanup={tagActions.cleanup}
      errors={errors}
      initialValues={{
        comment: tag.comment ?? "",
        definition: tag.definition ?? "",
        id: tag.id,
        kernel_opts: tag.kernel_opts ?? "",
        name: tag.name,
      }}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Submit",
        category: "Update tag form",
        label: "Update tag",
      }}
      onSubmit={(values) => {
        dispatch(tagActions.cleanup());
        dispatch(tagActions.update(values));
      }}
      onSuccess={(values) => {
        if (isAuto && values.definition !== tag.definition) {
          dispatch(
            messageActions.add(
              `Updated ${tag.name}. ${NewDefinitionMessage}`,
              NotificationSeverity.POSITIVE
            )
          );
        }
        closeSidePanel();
      }}
      saved={saved}
      saving={saving}
      submitLabel="Save changes"
      validationSchema={isAuto ? UpdateAutoTagFormSchema : UpdateTagFormSchema}
    >
      <UpdateTagFormFields id={id} />
    </FormikForm>
  );
};

export default UpdateTagForm;
