import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import DeleteTagForm from "../../components/DeleteTagForm";
import TagsDetailsHeader from "../../components/TagsDetailsHeader";
import UpdateTagForm from "../../components/UpdateTagForm";

import ModelNotFound from "@/app/base/components/ModelNotFound";
import PageContent from "@/app/base/components/PageContent";
import { useFetchActions, useWindowTitle } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag } from "@/app/store/tag/types";
import { TagMeta } from "@/app/store/tag/types";
import TagSummary from "@/app/tags/components/TagSummary";
import { isId } from "@/app/utils";

export enum Label {
  Title = "Tag details",
  AppliedTo = "Applied to",
  Comment = "Comment",
  Definition = "Definition (automatic tag)",
  DeleteButton = "Delete",
  EditButton = "Edit",
  Name = "Tag name",
  Options = "Kernel options",
  Update = "Last update",
}

const TagDetails = (): React.ReactElement => {
  const { openSidePanel } = useSidePanel();
  const id = useGetURLId(TagMeta.PK);
  const tag = useSelector((state: RootState) =>
    tagSelectors.getById(state, id)
  );
  const tagsLoading = useSelector(tagSelectors.loading);

  const onDelete = (id: Tag[TagMeta.PK], fromDetails?: boolean) => {
    openSidePanel({
      component: DeleteTagForm,
      title: "Delete tag",
      props: {
        fromDetails,
        id,
      },
    });
  };
  const onUpdate = (id: Tag[TagMeta.PK]) => {
    openSidePanel({
      component: UpdateTagForm,
      title: "Update Tag",
      props: {
        id,
      },
    });
  };
  useWindowTitle(tag ? `Tag: ${tag.name}` : "Tag");

  useFetchActions([tagActions.fetch]);

  return (
    <PageContent
      header={<TagsDetailsHeader onDelete={onDelete} onUpdate={onUpdate} />}
    >
      {!isId(id) || (!tagsLoading && !tag) ? (
        <ModelNotFound id={id} linkURL={urls.tags.index} modelName="tag" />
      ) : !tag || tagsLoading ? (
        <span data-testid="Spinner">
          <Spinner />
        </span>
      ) : (
        <div aria-label={Label.Title}>
          <TagSummary id={id} />
        </div>
      )}
    </PageContent>
  );
};

export default TagDetails;
