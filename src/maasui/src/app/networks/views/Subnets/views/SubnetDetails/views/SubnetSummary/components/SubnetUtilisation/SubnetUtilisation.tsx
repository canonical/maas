import { Row, Col } from "@canonical/react-components";

import Definition from "@/app/base/components/Definition";
import TitledSection from "@/app/base/components/TitledSection";
import type { SubnetStatistics } from "@/app/store/subnet/types";

type Props = {
  statistics: SubnetStatistics;
};

const SubnetUtilisation = ({ statistics }: Props): React.ReactElement => {
  return (
    <TitledSection title="Utilisation">
      <Row>
        <Col size={6}>
          <Definition
            description={`${statistics.total_addresses}`}
            label="Subnet addresses"
          />
          <Definition
            description={`${statistics.num_available} (${statistics.available_string})`}
            label="Availability"
          />
        </Col>
        <Col size={6}>
          <Definition description={statistics.usage_string} label="Used" />
        </Col>
      </Row>
    </TitledSection>
  );
};

export default SubnetUtilisation;
