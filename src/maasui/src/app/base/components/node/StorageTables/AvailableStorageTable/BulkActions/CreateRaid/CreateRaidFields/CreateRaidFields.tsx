import { Col, Input, Row, Select } from "@canonical/react-components";
import { useFormikContext } from "formik";

import FilesystemFields from "../../../FilesystemFields";
import type { CreateRaidValues } from "../CreateRaid";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import TagNameField from "@/app/base/components/TagNameField";
import DatastoreTable from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/DatastoreTable";
import { RAID_MODES } from "@/app/store/machine/constants";
import type { RaidMode } from "@/app/store/machine/constants";
import type { Machine } from "@/app/store/machine/types";
import type { Disk, Partition } from "@/app/store/types/node";
import { formatSize, isDisk } from "@/app/store/utils";

type Props = {
  storageDevices: (Disk | Partition)[];
  systemId: Machine["system_id"];
};

/**
 * Get the size of the RAID, given the RAID mode and number of active devices.
 * @param storageDevices - the selected storage devices.
 * @param raidMode - the selected RAID mode.
 * @param numActive - the number of active (i.e not spare) devices.
 * @returns the size of the RAID in bytes.
 */
const getRaidSize = (
  storageDevices: (Disk | Partition)[],
  raidMode: RaidMode,
  numActive: number
) => {
  // Min size is disk.available_size for disks, partition.size for partitions
  const minSize = Math.min(
    ...storageDevices.map((storageDevice) =>
      isDisk(storageDevice) ? storageDevice.available_size : storageDevice.size
    )
  );
  return raidMode.calculateSize(minSize, numActive);
};

export const CreateRaidFields = ({
  storageDevices,
  systemId,
}: Props): React.ReactElement => {
  const { handleChange, initialValues, setFieldValue, values } =
    useFormikContext<CreateRaidValues>();
  const {
    blockDeviceIds,
    level,
    partitionIds,
    spareBlockDeviceIds,
    sparePartitionIds,
  } = values;
  const availableRaidModes = RAID_MODES.filter(
    (raidMode) => storageDevices.length >= raidMode.minDevices
  );
  const selectedMode =
    RAID_MODES.find((raidMode) => raidMode.level === level) || RAID_MODES[0];
  const maxSpares = selectedMode.allowsSpares
    ? storageDevices.length - selectedMode.minDevices
    : 0;
  const numActive = blockDeviceIds.length + partitionIds.length;
  const numSpares = spareBlockDeviceIds.length + sparePartitionIds.length;
  const raidSize = getRaidSize(storageDevices, selectedMode, numActive);

  // Transform storage devices to include isSpare state
  const storageDevicesWithSpareState = storageDevices.map((device) => ({
    ...device,
    isSpare: isDisk(device)
      ? spareBlockDeviceIds.includes(device.id)
      : sparePartitionIds.includes(device.id),
  }));

  const handleSpareCheckbox = (
    storageDevice: Disk | Partition,
    isSpareDevice: boolean
  ) => {
    if (isDisk(storageDevice)) {
      if (isSpareDevice) {
        setFieldValue("blockDeviceIds", [
          ...blockDeviceIds,
          storageDevice.id,
        ]).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            "blockDeviceIds",
            "setFieldValue",
            reason as string
          );
        });
        setFieldValue(
          "spareBlockDeviceIds",
          spareBlockDeviceIds.filter((id) => id !== storageDevice.id)
        ).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            "spareBlockDeviceIds",
            "setFieldValue",
            reason as string
          );
        });
      } else {
        setFieldValue(
          "blockDeviceIds",
          blockDeviceIds.filter((id) => id !== storageDevice.id)
        ).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            "blockDeviceIds",
            "setFieldValue",
            reason as string
          );
        });
        setFieldValue("spareBlockDeviceIds", [
          ...spareBlockDeviceIds,
          storageDevice.id,
        ]).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            "spareBlockDeviceIds",
            "setFieldValue",
            reason as string
          );
        });
      }
    } else {
      if (isSpareDevice) {
        setFieldValue("partitionIds", [
          ...partitionIds,
          storageDevice.id,
        ]).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            "partitionIds",
            "setFieldValue",
            reason as string
          );
        });
        setFieldValue(
          "sparePartitionIds",
          sparePartitionIds.filter((id) => id !== storageDevice.id)
        ).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            "sparePartitionIds",
            "setFieldValue",
            reason as string
          );
        });
      } else {
        setFieldValue(
          "partitionIds",
          partitionIds.filter((id) => id !== storageDevice.id)
        ).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            "partitionIds",
            "setFieldValue",
            reason as string
          );
        });
        setFieldValue("sparePartitionIds", [
          ...sparePartitionIds,
          storageDevice.id,
        ]).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            "sparePartitionIds",
            "setFieldValue",
            reason as string
          );
        });
      }
    }
  };

  return (
    <>
      <Row>
        <Col size={12}>
          <FormikField label="Name" name="name" required type="text" />
          <FormikField
            component={Select}
            label="RAID level"
            name="level"
            onChange={(e) => {
              handleChange(e);
              // We reset the block/partition id values on RAID level change
              // to prevent stale values from existing in the form state.
              setFieldValue(
                "blockDeviceIds",
                initialValues.blockDeviceIds
              ).catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "blockDeviceIds",
                  "setFieldValue",
                  reason as string
                );
              });
              setFieldValue("partitionIds", initialValues.partitionIds).catch(
                (reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "partitionIds",
                    "setFieldValue",
                    reason as string
                  );
                }
              );
              setFieldValue(
                "spareBlockDeviceIds",
                initialValues.spareBlockDeviceIds
              ).catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "spareBlockDeviceIds",
                  "setFieldValue",
                  reason as string
                );
              });
              setFieldValue(
                "sparePartitionIds",
                initialValues.sparePartitionIds
              ).catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "sparePartitionIds",
                  "setFieldValue",
                  reason as string
                );
              });
            }}
            options={availableRaidModes.map((raidMode) => ({
              label: raidMode.label,
              key: raidMode.level,
              value: raidMode.level,
            }))}
          />
          <Input
            aria-label="Size"
            data-testid="raid-size"
            disabled
            label="Size"
            type="text"
            value={formatSize(raidSize)}
          />
          <TagNameField />
        </Col>
        <Col size={12}>
          <FilesystemFields systemId={systemId} />
        </Col>
      </Row>
      <Row>
        <Col size={12}>
          <DatastoreTable
            data={storageDevicesWithSpareState}
            handleSpareCheckbox={handleSpareCheckbox}
            maxSpares={maxSpares}
            numSpares={numSpares}
          />
        </Col>
      </Row>
    </>
  );
};

export default CreateRaidFields;
