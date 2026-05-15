import { Col, Input, Row } from "@canonical/react-components";

import FilesystemFields from "../../FilesystemFields";

import type { Machine } from "@/app/store/machine/types";
import type { Partition } from "@/app/store/types/node";
import { formatSize, formatType } from "@/app/store/utils";

type Props = {
  partition: Partition;
  systemId: Machine["system_id"];
};

export const EditPartitionFields = ({
  partition,
  systemId,
}: Props): React.ReactElement => {
  return (
    <Row>
      <Col size={12}>
        <Input disabled label="Name" type="text" value={partition.name} />
        <Input
          disabled
          label="Type"
          type="text"
          value={formatType(partition)}
        />
        <Input
          disabled
          label="Size"
          type="text"
          value={formatSize(partition.size)}
        />
      </Col>
      <Col size={12}>
        <FilesystemFields systemId={systemId} />
      </Col>
    </Row>
  );
};

export default EditPartitionFields;
