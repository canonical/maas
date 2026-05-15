import { Select } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { Filesystem } from "@/app/store/types/node";
import { usesStorage } from "@/app/store/utils";

type FilesystemValues = {
  fstype: Filesystem["fstype"];
  mountOptions: Filesystem["mount_options"];
  mountPoint: Filesystem["mount_point"];
};

type Props = {
  systemId: Machine["system_id"];
};

export const FilesystemFields = ({
  systemId,
}: Props): React.ReactElement | null => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const { handleChange, setFieldTouched, setFieldValue, values } =
    useFormikContext<FilesystemValues>();

  if (isMachineDetails(machine)) {
    const fsOptions = machine.supported_filesystems
      .filter((fs) => usesStorage(fs.key))
      .map((fs) => ({
        label: fs.ui,
        value: fs.key,
      }));
    const swapSelected = values.fstype === "swap";
    const disableMountPoint = !values.fstype || swapSelected;
    const disableMountOptions = !values.fstype;

    return (
      <>
        <FormikField<typeof Select>
          component={Select}
          label="Filesystem"
          name="fstype"
          onChange={(e) => {
            handleChange(e);
            // Swap filesystems must be mounted at "none" instead of an empty
            // string in order to work with the API.
            if (e.target.value === "swap") {
              setFieldTouched("mountPoint").catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "mountPoint",
                  "setFieldTouched",
                  reason as string
                );
              });
              setFieldValue("mountPoint", "none").catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "mountPoint",
                  "setFieldValue",
                  reason as string
                );
              });
            } else {
              setFieldValue("mountPoint", "").catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "mountPoint",
                  "setFieldValue",
                  reason as string
                );
              });
            }
          }}
          options={[
            {
              label: "Select filesystem type",
              value: "",
              disabled: true,
            },
            {
              label: "Unformatted",
              value: "",
            },
            ...fsOptions,
          ]}
        />
        <FormikField
          disabled={disableMountPoint}
          label="Mount point"
          name="mountPoint"
          placeholder="/path/to/filesystem"
          type="text"
        />
        <FormikField
          disabled={disableMountOptions}
          help={
            disableMountOptions
              ? undefined
              : 'Comma-separated list without spaces, e.g. "noexec,size=1024k".'
          }
          label="Mount options"
          name="mountOptions"
          type="text"
        />
      </>
    );
  }
  return null;
};

export default FilesystemFields;
