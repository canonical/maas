import { Col, Row } from "@canonical/react-components";

import EditSpace from "../EditSpace";

import Definition from "@/app/base/components/Definition";
import EditableSection from "@/app/base/components/EditableSection";
import type { Space } from "@/app/store/space/types";

const SpaceSummary = ({ space }: { space: Space }): React.ReactElement => {
  return (
    <EditableSection
      hasSidebarTitle
      renderContent={(editing, setEditing) =>
        editing ? (
          <EditSpace
            handleDismiss={() => {
              setEditing(false);
            }}
            space={space}
          />
        ) : (
          <Row>
            <Col size={6}>
              <Definition label="Name">{space.name}</Definition>
              <Definition label="Description">{space.description}</Definition>
            </Col>
          </Row>
        )
      }
      title="Space summary"
    />
  );
};

export default SpaceSummary;
