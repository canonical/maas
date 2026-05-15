import { MainToolbar } from "@canonical/maas-react-components";
import { Button } from "@canonical/react-components";

import AddTagForm from "../AddTagForm";

import SearchBox from "@/app/base/components/SearchBox";
import SegmentedControl from "@/app/base/components/SegmentedControl";
import { useSidePanel } from "@/app/base/side-panel-context";
import { TagSearchFilter } from "@/app/store/tag/selectors";

export type Props = {
  filter: TagSearchFilter;
  setFilter: (filter: TagSearchFilter) => void;
  searchText: string;
  setSearchText: (searchText: string) => void;
};

export enum Label {
  CreateButton = "Create new tag",
  EditButton = "Edit",
  DeleteButton = "Delete",
  Header = "Tags header",
  All = "All tags",
  Manual = "Manual tags",
  Auto = "Automatic tags",
}

export const TagsListHeader = ({
  filter,
  setFilter,
  searchText,
  setSearchText,
}: Props): React.ReactElement => {
  const { openSidePanel } = useSidePanel();
  return (
    <MainToolbar>
      <MainToolbar.Title>Tags</MainToolbar.Title>
      <MainToolbar.Controls>
        <>
          <SearchBox
            externallyControlled
            onChange={setSearchText}
            value={searchText}
          />
          <SegmentedControl
            aria-label="tag filter"
            onSelect={setFilter}
            options={[
              {
                label: Label.All,
                value: TagSearchFilter.All,
              },
              {
                label: Label.Manual,
                value: TagSearchFilter.Manual,
              },
              {
                label: Label.Auto,
                value: TagSearchFilter.Auto,
              },
            ]}
            selected={filter}
          />
        </>
        <Button
          appearance="positive"
          onClick={() => {
            openSidePanel({
              component: AddTagForm,
              title: "Create new tag",
            });
          }}
        >
          {Label.CreateButton}
        </Button>
      </MainToolbar.Controls>
    </MainToolbar>
  );
};

export default TagsListHeader;
