import type { ReactElement } from "react";
import { useEffect, useState } from "react";

import { Col, NotificationSeverity, Row } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import AddTagForm from "./AddTagForm";
import TagFormFields from "./TagFormFields";
import type { TagFormValues } from "./types";

import ActionForm from "@/app/base/components/ActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineEventErrors } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { messageActions } from "@/app/store/message";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import { NodeActions } from "@/app/store/types/node";
import TagSummary from "@/app/tags/components/TagSummary";

type TagFormProps = {
  isViewingDetails: boolean;
  isViewingMachineConfig?: boolean;
  closeForm?: () => void;
};

export enum Label {
  Saved = "Saved all tag changes.",
}

const TagFormSchema = Yup.object().shape({
  added: Yup.array().of(Yup.string()),
  removed: Yup.array().of(Yup.string()),
});

export type TagFormSecondaryContent = "addTag" | "tagDetails" | null;

export const TagForm = ({
  isViewingDetails,
  isViewingMachineConfig = false,
  closeForm,
}: TagFormProps): ReactElement => {
  const dispatch = useDispatch();
  const searchFilter = FilterMachines.filtersToString(
    FilterMachines.queryStringToFilters(location.search)
  );

  const selectedMachines = useSelector(machineSelectors.selected);
  const { selectedCount } = useMachineSelectedCount(
    FilterMachines.parseFetchFilters(searchFilter)
  );
  const {
    dispatch: dispatchForSelectedMachines,
    actionErrors: errors,
    ...actionProps
  } = useSelectedMachinesActionsDispatch({ selectedMachines, searchFilter });
  const tagsLoaded = useSelector(tagSelectors.loaded);
  const [newTags, setNewTags] = useState<Tag[TagMeta.PK][]>([]);

  let formErrors: Record<string, string[] | string> | null = null;
  if (errors && typeof errors === "object" && "name" in errors) {
    formErrors = {
      ...errors,
      added: errors.name,
    } as Record<string, string[] | string>;
    delete formErrors.name;
  }

  const [newTagName, setNewTagName] = useState<string | null>(null);
  const { setSidePanelSize, closeSidePanel } = useSidePanel();

  const [secondaryContent, setSecondaryContent] =
    useState<TagFormSecondaryContent>(null);
  useEffect(() => {
    // increase the side panel size when the secondary content is open
    if (secondaryContent !== null) {
      setSidePanelSize("large");
    } else {
      setSidePanelSize("regular");
    }
  }, [secondaryContent, setSidePanelSize]);

  const [tagDetails, setTagDetails] = useState<Tag | null>(null);

  const toggleTagDetails = (tag: Tag | null) => {
    setTagDetails(tag);
    if (tag) {
      setSecondaryContent("tagDetails");
    } else {
      setSecondaryContent(null);
    }
  };

  return (
    <Row>
      {secondaryContent === "addTag" ? (
        <Col size={6}>
          <AddTagForm
            isViewingDetails={isViewingDetails}
            isViewingMachineConfig={isViewingMachineConfig}
            name={newTagName}
            onCancel={() => {
              setSecondaryContent(null);
            }}
            onTagCreated={(tag) => {
              setNewTagName(null);
              setNewTags([...newTags, tag.id]);
              setSecondaryContent(null);
            }}
            searchFilter={searchFilter}
            selectedMachines={selectedMachines}
          />
        </Col>
      ) : null}
      {secondaryContent === "tagDetails" && tagDetails ? (
        <Col size={6}>
          <h4>{tagDetails.name}</h4>
          <TagSummary id={tagDetails.id} narrow />
        </Col>
      ) : null}
      <Col size={secondaryContent !== null ? 6 : 12}>
        <ActionForm<TagFormValues, MachineEventErrors>
          actionName={NodeActions.TAG}
          cleanup={machineActions.cleanup}
          errors={formErrors || errors}
          initialValues={{
            added: [],
            removed: [],
          }}
          loaded={tagsLoaded}
          modelName="machine"
          onCancel={closeForm ? closeForm : closeSidePanel}
          onSaveAnalytics={{
            action: "Submit",
            category: `Machine ${
              isViewingDetails ? "details" : "list"
            } action form`,
            label: "Tag",
          }}
          onSubmit={(values) => {
            dispatch(machineActions.cleanup());
            if (values.added.length) {
              dispatchForSelectedMachines(machineActions.tag, {
                tags: values.added.map((id) => Number(id)),
              });
            }
            if (values.removed.length) {
              dispatchForSelectedMachines(machineActions.untag, {
                tags: values.removed.map((id) => Number(id)),
              });
            }
          }}
          onSuccess={() => {
            if (closeForm) {
              closeForm();
            } else {
              closeSidePanel();
            }
            dispatch(
              messageActions.add(Label.Saved, NotificationSeverity.POSITIVE)
            );
          }}
          selectedCount={selectedCount ?? 0}
          showProcessingCount={!isViewingMachineConfig}
          submitLabel="Save tag changes"
          validationSchema={TagFormSchema}
          {...actionProps}
        >
          <TagFormFields
            isViewingDetails={isViewingDetails}
            isViewingMachineConfig={isViewingMachineConfig}
            newTags={newTags}
            searchFilter={searchFilter}
            selectedCount={selectedCount}
            selectedMachines={selectedMachines}
            setNewTagName={setNewTagName}
            setNewTags={setNewTags}
            setSecondaryContent={setSecondaryContent}
            toggleTagDetails={toggleTagDetails}
          />
        </ActionForm>
      </Col>
    </Row>
  );
};

export default TagForm;
