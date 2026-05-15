import { useEffect } from "react";

import { Button, Card, Spinner } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { Disk, ComposeFormValues } from "../ComposeForm";

import PoolSelect from "./PoolSelect";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import TagNameField from "@/app/base/components/TagNameField";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  defaultDisk: Disk;
  hostId: Pod["id"];
};

export const StorageTable = ({
  defaultDisk,
  hostId,
}: Props): React.ReactElement => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  );
  const composingPods = useSelector(podSelectors.composing);
  const { handleChange, setFieldTouched, setFieldValue, touched, values } =
    useFormikContext<ComposeFormValues>();
  const { bootDisk, disks } = values;

  // Ensure initial disk is always validated correctly.
  useEffect(() => {
    if (disks.length && !(touched.disks?.length && touched.disks[0].size)) {
      setFieldTouched("disks[0].size", true, true).catch((reason: unknown) => {
        throw new FormikFieldChangeError(
          "disks[0].size",
          "setFieldTouched",
          reason as string
        );
      });
    }
  }, [disks, setFieldTouched, touched]);

  const addDisk = () => {
    const ids = disks.map((disk) => disk.id);
    let id = 0;
    while (ids.includes(id)) {
      id++;
    }
    setFieldTouched(`disks[${disks.length}].size`, true, true).catch(
      (reason: unknown) => {
        throw new FormikFieldChangeError(
          `disks[${disks.length}].size`,
          "setFieldTouched",
          reason as string
        );
      }
    );
    setFieldValue("disks", [...disks, { ...defaultDisk, id }], true).catch(
      (reason: unknown) => {
        throw new FormikFieldChangeError(
          "disks",
          "setFieldValue",
          reason as string
        );
      }
    );
  };

  const removeDisk = (id: number) => {
    const filteredDisks = disks.filter((disk) => disk.id !== id);
    setFieldValue("disks", filteredDisks).catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "disks",
        "setFieldValue",
        reason as string
      );
    });

    // If boot disk is removed, set boot to first disk in the remaining array.
    if (!filteredDisks.some((disk) => disk.id === bootDisk)) {
      setFieldValue("bootDisk", filteredDisks[0]?.id).catch(
        (reason: unknown) => {
          throw new FormikFieldChangeError(
            "bootDisk",
            "setFieldValue",
            reason as string
          );
        }
      );
    }
  };

  if (!!pod) {
    const disabled = !!composingPods.length;

    return (
      <>
        <div className="u-flex--between">
          <h4>Storage configuration</h4>
          <Button
            data-testid="add-disk"
            disabled={disabled}
            hasIcon
            onClick={addDisk}
            type="button"
          >
            <i className="p-icon--plus"></i>
            <span>Add disk</span>
          </Button>
        </div>
        {disks.map((disk, i) => {
          const isBootDisk = disk.id === bootDisk;
          return (
            <Card aria-label="disk" key={disk.id}>
              <FormikField
                caution={
                  isBootDisk && disk.size < 8
                    ? "Ubuntu typically requires 8GB minimum."
                    : undefined
                }
                label="Size (GB)"
                min="1"
                name={`disks[${i}].size`}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  const value = parseFloat(e.target.value) || "";
                  if (value === "" || value >= 0) {
                    handleChange(e);
                    setFieldTouched(`disks[${i}].size`, true, true).catch(
                      (reason: unknown) => {
                        throw new FormikFieldChangeError(
                          `disks[${i}].size`,
                          "setFieldTouched",
                          reason as string
                        );
                      }
                    );
                    setFieldValue(`disks[${i}].size`, value).catch(
                      (reason: unknown) => {
                        throw new FormikFieldChangeError(
                          `disks[${i}].size`,
                          "setFieldValue",
                          reason as string
                        );
                      }
                    );
                  }
                }}
                step="any"
                type="number"
              />
              <label>Location</label>
              <PoolSelect
                disk={disk}
                hostId={hostId}
                selectPool={(poolName?: string) => {
                  setFieldValue(`disks[${i}].location`, poolName).catch(
                    (reason: unknown) => {
                      throw new FormikFieldChangeError(
                        `disks[${i}].location`,
                        "setFieldValue",
                        reason as string
                      );
                    }
                  );
                }}
              />
              <TagNameField
                label={"Tags"}
                name={`disks[${i}].tags`}
                placeholder="Add tags"
              />
              <FormikField
                aria-label="Boot"
                checked={bootDisk === disk.id}
                label="Boot"
                labelClassName="p-radio--inline u-nudge-right--small"
                name="bootDisk"
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  handleChange(e);
                  setFieldValue("bootDisk", disk.id).catch(
                    (reason: unknown) => {
                      throw new FormikFieldChangeError(
                        "bootDisk",
                        "setFieldValue",
                        reason as string
                      );
                    }
                  );
                }}
                type="radio"
              />

              {disks.length === 1 || !!composingPods.length ? null : (
                <div className="u-align--right">
                  <Button
                    data-testid="remove-disk"
                    disabled={!!composingPods.length}
                    onClick={() => {
                      removeDisk(disk.id);
                    }}
                    type="button"
                  >
                    Remove
                  </Button>
                </div>
              )}
            </Card>
          );
        })}
      </>
    );
  }
  return <Spinner text="Loading..." />;
};

export default StorageTable;
