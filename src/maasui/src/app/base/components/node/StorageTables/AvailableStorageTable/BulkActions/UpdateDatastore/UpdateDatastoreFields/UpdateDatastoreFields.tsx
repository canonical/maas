import { Col, Input, Row, Select } from "@canonical/react-components";
import { useFormikContext } from "formik";

import type { UpdateDatastoreValues } from "../UpdateDatastore";

import FormikField from "@/app/base/components/FormikField";
import DatastoreTable from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/DatastoreTable";
import type { Disk, Partition } from "@/app/store/types/node";
import { formatSize } from "@/app/store/utils";

type Props = {
  datastores: Disk[];
  storageDevices: (Disk | Partition)[];
};

export const UpdateDatastoreFields = ({
  datastores,
  storageDevices,
}: Props): React.ReactElement => {
  const { values } = useFormikContext<UpdateDatastoreValues>();
  const selectedDatastore = datastores.find(
    (datastore) => datastore.id === Number(values.datastore)
  );
  const totalSize = storageDevices.reduce(
    (sum, device) => (sum += device.size),
    0
  );

  return (
    <Row>
      <Col size={12}>
        <DatastoreTable data={storageDevices} />
      </Col>
      <Col size={12}>
        <FormikField
          component={Select}
          label="Datastore"
          name="datastore"
          options={datastores.map((datastore) => ({
            label: datastore.name,
            key: datastore.id,
            value: datastore.id,
          }))}
        />
        <Input
          aria-label="Mount point"
          data-testid="datastore-mount-point"
          disabled
          label="Mount point"
          type="text"
          value={selectedDatastore?.filesystem?.mount_point || ""}
        />
        <Input
          aria-label="Size to add"
          data-testid="size-to-add"
          disabled
          label="Size to add"
          type="text"
          value={`${formatSize(totalSize)}`}
        />
      </Col>
    </Row>
  );
};

export default UpdateDatastoreFields;
