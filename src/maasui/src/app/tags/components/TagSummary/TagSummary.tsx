import { CodeSnippet, Col, Row, Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import AppliedTo from "../AppliedTo";

import Definition from "@/app/base/components/Definition";
import ModelNotFound from "@/app/base/components/ModelNotFound";
import { useFetchActions } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import { isId } from "@/app/utils";

type Props = {
  id: Tag[TagMeta.PK] | null;
  narrow?: boolean;
};

export enum Label {
  AppliedTo = "Applied to",
  Comment = "Comment",
  Definition = "Definition (automatic tag)",
  Name = "Tag name",
  Options = "Kernel options",
  Update = "Last update",
}

const TagSummary = ({ id, narrow }: Props): React.ReactElement => {
  const tag = useSelector((state: RootState) =>
    tagSelectors.getById(state, id)
  );
  const tagsLoading = useSelector(tagSelectors.loading);

  useFetchActions([tagActions.fetch]);

  if (!isId(id) || (!tagsLoading && !tag)) {
    return <ModelNotFound id={id} linkURL={urls.tags.index} modelName="tag" />;
  }

  if (!tag || tagsLoading) {
    return (
      <span data-testid="Spinner">
        <Spinner />
      </span>
    );
  }

  return (
    <>
      <Row>
        {narrow ? null : (
          <Col size={2}>
            <Definition description={tag.name} label={Label.Name} />
          </Col>
        )}
        <Col size={narrow ? 3 : 2}>
          <Definition description={tag.updated} label={Label.Update} />
        </Col>
        <Col size={narrow ? 3 : 2}>
          <Definition label={Label.AppliedTo}>
            <AppliedTo id={id} />
          </Definition>
        </Col>
        <Col size={6}>
          <Definition description={tag.comment} label={Label.Comment} />
        </Col>
      </Row>
      <hr className="u-sv1" />
      <Row>
        <Col size={narrow ? 12 : 6}>
          <p className="u-text--muted">{Label.Options}</p>
          {tag.kernel_opts ? (
            <CodeSnippet
              blocks={[
                {
                  code: tag.kernel_opts,
                },
              ]}
            />
          ) : (
            <p>None</p>
          )}
        </Col>
        <Col size={narrow ? 12 : 6}>
          <p className="u-text--muted">{Label.Definition}</p>
          {tag.definition ? (
            <CodeSnippet
              blocks={[
                {
                  code: tag.definition,
                },
              ]}
            />
          ) : (
            <p>None</p>
          )}
        </Col>
      </Row>
    </>
  );
};

export default TagSummary;
