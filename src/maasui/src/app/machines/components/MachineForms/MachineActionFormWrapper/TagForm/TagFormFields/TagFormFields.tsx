import type { Dispatch, ReactNode, SetStateAction } from "react";
import { useEffect } from "react";

import { Icon, Spinner } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { TagFormSecondaryContent } from "../TagForm";
import TagFormChanges from "../TagFormChanges";
import {
  useFetchTagsForSelected,
  useSelectedTags,
  useUnchangedTags,
} from "../hooks";
import type { TagFormValues } from "../types";

import TagField from "@/app/base/components/TagField";
import type { Tag as TagSelectorTag } from "@/app/base/components/TagSelector/TagSelector";
import type { MachineActionFormProps } from "@/app/machines/types";
import type { SelectedMachines } from "@/app/store/machine/types";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import { getTagCounts } from "@/app/store/tag/utils";

const hasKernelOptions = (tags: Tag[], tag: TagSelectorTag) =>
  !!tags.find(({ id }) => tag.id === id)?.kernel_opts;

type Props = Pick<MachineActionFormProps, "searchFilter"> & {
  newTags: Tag[TagMeta.PK][];
  setNewTags: (tags: Tag[TagMeta.PK][]) => void;
  setNewTagName: (name: string) => void;
  isViewingDetails?: boolean;
  isViewingMachineConfig?: boolean;
  selectedMachines?: SelectedMachines | null;
  selectedCount?: number | null;
  toggleTagDetails: (tag: Tag | null) => void;
} & {
  setSecondaryContent: Dispatch<SetStateAction<TagFormSecondaryContent>>;
};

export enum Label {
  AddTag = "Create a new tag",
  TagInput = "Search existing or add new tags",
}

export const TagFormFields = ({
  newTags,
  setNewTagName,
  searchFilter,
  selectedMachines,
  setSecondaryContent,
  selectedCount,
  toggleTagDetails,
}: Props): React.ReactElement => {
  const selectedTags = useSelectedTags("added");
  const { setFormikState } = useFormikContext<TagFormValues>();
  const { tags, loading: tagsLoading } = useFetchTagsForSelected({
    selectedMachines,
    searchFilter,
  });
  const allManualTags = useSelector(tagSelectors.getManual);
  const tagIdsAndCounts = getTagCounts(tags);
  // Tags can't be added if they already exist on all machines or already in
  // the added/removed lists.
  const unchangedTags = useUnchangedTags(allManualTags);
  const availableTags = unchangedTags.filter(
    (tag) => tagIdsAndCounts?.get(tag.id) !== selectedCount
  );

  useEffect(() => {
    // add new tags to the formik state values
    if (newTags.length > 0) {
      setFormikState((previousState) => {
        const tagsToAdd = newTags
          .map((tag) => String(tag))
          // filter out tags that are already in the added list
          .filter(
            (tag) => !previousState.values.added.find((id) => id === tag)
          );
        return {
          ...previousState,
          values: {
            ...previousState.values,
            added: [...previousState.values.added, ...tagsToAdd],
          },
        };
      });
    }
  }, [newTags, setFormikState]);

  return (
    <>
      <TagField
        externalSelectedTags={selectedTags}
        generateDropdownEntry={(
          tag: TagSelectorTag,
          highlightedName: ReactNode
        ) => (
          <div className="u-flex--between">
            <span>{highlightedName}</span>
            {hasKernelOptions(tags, tag) ? (
              <span
                aria-label="with kernel options"
                className="u-nudge-left--small"
              >
                <Icon name="tick" />
              </span>
            ) : null}
          </div>
        )}
        header={
          <div className="u-flex--between p-text--x-small-capitalised u-nudge-down--x-small">
            <span>Tag name</span>
            <span>Kernel options</span>
          </div>
        }
        label={Label.TagInput}
        name="added"
        onAddNewTag={(name) => (_) => {
          setNewTagName(name);
          setSecondaryContent("addTag");
        }}
        placeholder=""
        showSelectedTags={false}
        storedValue="id"
        tags={availableTags.map(({ id, name }) => ({ id, name }))}
      />
      {tags.length === 0 && tagsLoading ? (
        <Spinner text="Loading tags..." />
      ) : (
        <TagFormChanges
          newTags={newTags}
          selectedCount={selectedCount}
          tags={tags}
          toggleTagDetails={toggleTagDetails}
        />
      )}
    </>
  );
};

export default TagFormFields;
