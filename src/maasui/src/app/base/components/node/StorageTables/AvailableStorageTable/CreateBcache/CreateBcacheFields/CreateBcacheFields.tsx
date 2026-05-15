import { Col, Input, Row, Select } from "@canonical/react-components";

import FilesystemFields from "../../FilesystemFields";

import FormikField from "@/app/base/components/FormikField";
import TagNameField from "@/app/base/components/TagNameField";
import type { Machine } from "@/app/store/machine/types";
import { BcacheModes } from "@/app/store/machine/types";
import type { Disk, Partition } from "@/app/store/types/node";
import { formatSize } from "@/app/store/utils";

type Props = {
  cacheSets: Disk[];
  storageDevice: Disk | Partition;
  systemId: Machine["system_id"];
};

export const CreateBcacheFields = ({
  cacheSets,
  storageDevice,
  systemId,
}: Props): React.ReactElement => {
  return (
    <Row>
      <Col size={12}>
        <FormikField label="Name" name="name" required type="text" />
        <Input
          disabled
          label="Size"
          type="text"
          value={formatSize(storageDevice.size)}
        />
        <FormikField
          component={Select}
          label="Cache set"
          name="cacheSetId"
          options={cacheSets.map((cacheSet) => ({
            key: cacheSet.id,
            label: cacheSet.name,
            value: cacheSet.id,
          }))}
        />
        <FormikField
          component={Select}
          label="Cache mode"
          name="cacheMode"
          options={[
            { label: BcacheModes.WRITE_BACK, value: BcacheModes.WRITE_BACK },
            {
              label: BcacheModes.WRITE_THROUGH,
              value: BcacheModes.WRITE_THROUGH,
            },
            {
              label: BcacheModes.WRITE_AROUND,
              value: BcacheModes.WRITE_AROUND,
            },
          ]}
        />
        <TagNameField />
      </Col>
      <Col size={12}>
        <FilesystemFields systemId={systemId} />
      </Col>
    </Row>
  );
};

export default CreateBcacheFields;
