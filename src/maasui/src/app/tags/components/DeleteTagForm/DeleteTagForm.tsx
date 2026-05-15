import { Col, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router";

import DeleteTagFormWarnings from "./DeleteTagFormWarnings";

import FormikForm from "@/app/base/components/FormikForm";
import { useScrollToTop } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject, SyncNavigateFunction } from "@/app/base/types";
import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";

type Props = {
  fromDetails?: boolean;
  id: Tag[TagMeta.PK];
};

export const DeleteTagForm = ({
  fromDetails = false,
  id,
}: Props): React.ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const navigate: SyncNavigateFunction = useNavigate();
  const saved = useSelector(tagSelectors.saved);
  const saving = useSelector(tagSelectors.saving);
  const errors = useSelector(tagSelectors.errors);
  const tag = useSelector((state: RootState) =>
    tagSelectors.getById(state, id)
  );

  useScrollToTop();
  const onCancel = () => {
    closeSidePanel();
    if (fromDetails) {
      // Explicitly return to the page they user came from in case they have opened
      // the list of machines.
      navigate({ pathname: urls.tags.tag.index({ id: id }) });
    } else {
      navigate({ pathname: urls.tags.index });
    }
  };
  if (!tag) {
    return null;
  }
  return (
    <FormikForm<EmptyObject>
      aria-label="Delete tag"
      cleanup={tagActions.cleanup}
      errors={errors}
      initialValues={{}}
      onCancel={onCancel}
      onSaveAnalytics={{
        action: "Delete",
        category: "Delete tag form",
        label: "Delete tag",
      }}
      onSubmit={() => {
        dispatch(tagActions.cleanup());
        dispatch(tagActions.delete(tag.id));
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      savedRedirect={urls.tags.index}
      saving={saving}
      submitAppearance="negative"
      submitLabel="Delete"
    >
      <Row>
        <Col size={12}>
          <p className="u-nudge-down--small">
            {`${tag.name} will be deleted${
              tag.machine_count > 0
                ? " and unassigned from every tagged machine"
                : ""
            }. Are you sure?`}
          </p>
        </Col>
        <Col size={12}>
          <DeleteTagFormWarnings id={id} />
        </Col>
      </Row>
    </FormikForm>
  );
};

export default DeleteTagForm;
