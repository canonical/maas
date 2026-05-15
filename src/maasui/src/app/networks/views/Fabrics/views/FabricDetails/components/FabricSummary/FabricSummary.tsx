import type { ReactElement } from "react";

import { Col, Row } from "@canonical/react-components";

import EditFabric from "../EditFabric";

import FabricController from "./FabricController";

import Definition from "@/app/base/components/Definition";
import EditableSection from "@/app/base/components/EditableSection";
import type { Fabric } from "@/app/store/fabric/types";

const FabricSummary = ({ fabric }: { fabric: Fabric }): ReactElement => {
  return (
    <EditableSection
      hasSidebarTitle
      renderContent={(editing, setEditing) =>
        editing ? (
          <EditFabric
            handleDismiss={() => {
              setEditing(false);
            }}
            id={fabric.id}
          />
        ) : (
          <Row>
            <Col size={6}>
              <Definition description={fabric.name} label="Name" />
              <Definition
                description={fabric.description}
                label="Description"
              />
              <FabricController id={fabric.id} />
            </Col>
          </Row>
        )
      }
      title="Fabric summary"
    />
  );
};

export default FabricSummary;
