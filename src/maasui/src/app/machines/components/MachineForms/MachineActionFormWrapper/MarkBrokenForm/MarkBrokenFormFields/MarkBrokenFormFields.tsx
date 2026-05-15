import { Col, Row } from "@canonical/react-components";
import pluralize from "pluralize";

import FormikField from "@/app/base/components/FormikField";

type Props = {
  selectedCount: number;
};

export const MarkBrokenFormFields = ({
  selectedCount,
}: Props): React.ReactElement => (
  <>
    <Row>
      <Col size={12}>
        <FormikField
          label={`Add error description to ${selectedCount} ${pluralize(
            "machine",
            selectedCount
          )}`}
          name="comment"
          type="text"
        />
      </Col>
    </Row>
    <Row>
      <Col size={12}>
        <p className="p-form__help u-no-margin--top">
          The error description will be visible under the status of each machine
          in the machine listing. It will be removed when the machine is marked
          as fixed.
        </p>
      </Col>
    </Row>
  </>
);

export default MarkBrokenFormFields;
