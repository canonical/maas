import { ExternalLink } from "@canonical/maas-react-components";
import { Col, Row } from "@canonical/react-components";
import { useSelector } from "react-redux";

import Definition from "@/app/base/components/Definition";
import FormikField from "@/app/base/components/FormikField";
import docsUrls from "@/app/base/docsUrls";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import AppliedTo from "@/app/tags/components/AppliedTo";
import DefinitionField from "@/app/tags/components/DefinitionField";
import KernelOptionsField from "@/app/tags/components/KernelOptionsField";
import { Label } from "@/app/tags/views/TagDetails";
import { formatUtcDatetime } from "@/app/utils/time";

type Props = {
  id: Tag[TagMeta.PK];
};

export const UpdateTagFormFields = ({
  id,
}: Props): React.ReactElement | null => {
  const tag = useSelector((state: RootState) =>
    tagSelectors.getById(state, id)
  );

  if (!tag) {
    return null;
  }

  return (
    <>
      <Row>
        <Col size={12}>
          <FormikField
            label={Label.Name}
            name="name"
            placeholder="Enter a name for the tag."
            required
            type="text"
          />
        </Col>
        <Col size={12}>
          <Definition
            description={formatUtcDatetime(tag.updated)}
            label={Label.Update}
          />
        </Col>
        <Col size={12}>
          <Definition label={Label.AppliedTo}>
            <AppliedTo id={id} />
          </Definition>
        </Col>
        <Col size={12}>
          <FormikField
            label={Label.Comment}
            name="comment"
            placeholder="Add a comment as an explanation for this tag."
            type="text"
          />
        </Col>
      </Row>
      <hr className="u-sv1" />
      <Row>
        <Col size={12}>
          <KernelOptionsField id={id} />
        </Col>
        <Col size={12}>
          {!tag.definition ? (
            <Definition label={Label.Definition}>
              <span className="p-form-help-text">
                This is a manual tag. Definitions cannot be added to manual
                tags. To learn more about this, check our{" "}
                <ExternalLink to={docsUrls.tagsXpathExpressions}>
                  XPath expressions documentation
                </ExternalLink>
                .
              </span>
            </Definition>
          ) : (
            <DefinitionField id={id} />
          )}
        </Col>
      </Row>
    </>
  );
};

export default UpdateTagFormFields;
