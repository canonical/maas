import { useId, useState } from "react";

import { useSelector } from "react-redux";

import DeleteTagForm from "../../components/DeleteTagForm";
import TagTable from "../../components/TagTable";
import TagsListHeader from "../../components/TagsListHeader";
import UpdateTagForm from "../../components/UpdateTagForm";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { RootState } from "@/app/store/root/types";
import tagSelectors, { TagSearchFilter } from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";

export enum Label {
  Title = "Tag list",
}

const TagList = (): React.ReactElement => {
  useWindowTitle("Tags");

  const { openSidePanel } = useSidePanel();
  const [filter, setFilter] = useState(TagSearchFilter.All);
  const [searchText, setSearchText] = useState("");
  const tags = useSelector((state: RootState) =>
    tagSelectors.search(state, searchText, filter)
  );

  const tableId = useId();
  const onDelete = (id: Tag[TagMeta.PK], fromDetails?: boolean) => {
    openSidePanel({
      component: DeleteTagForm,
      title: "Delete tag",
      props: { fromDetails, id },
    });
  };
  const onUpdate = (id: Tag[TagMeta.PK]) => {
    openSidePanel({
      component: UpdateTagForm,
      title: "Update tag",
      props: { id },
    });
  };

  return (
    <PageContent
      header={
        <TagsListHeader
          filter={filter}
          searchText={searchText}
          setFilter={setFilter}
          setSearchText={setSearchText}
        />
      }
    >
      <div aria-label={Label.Title}>
        <div className="u-nudge-down">
          <TagTable
            filter={filter}
            id={tableId}
            onDelete={onDelete}
            onUpdate={onUpdate}
            searchText={searchText}
            tags={tags}
          />
        </div>
      </div>
    </PageContent>
  );
};

export default TagList;
