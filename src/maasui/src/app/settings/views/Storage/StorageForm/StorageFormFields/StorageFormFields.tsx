import { Select } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { StorageFormValues } from "../types";

import FormikField from "@/app/base/components/FormikField";
import configSelectors from "@/app/store/config/selectors";
import { StorageLayout } from "@/app/store/types/enum";
import { isVMWareLayout } from "@/app/store/utils";

const StorageFormFields = (): React.ReactElement => {
  const { values } = useFormikContext<StorageFormValues>();
  const storageLayoutOptions =
    useSelector(configSelectors.storageLayoutOptions) || [];

  return (
    <>
      <FormikField
        component={Select}
        help="Storage layout that is applied to a node when it is commissioned."
        label="Default storage layout"
        name="default_storage_layout"
        options={storageLayoutOptions}
      />
      {values.default_storage_layout === StorageLayout.BLANK && (
        <p
          className="p-form-validation__message"
          data-testid="blank-layout-warning"
        >
          <i className="p-icon--warning" />
          <strong className="u-nudge-right--x-small">Caution:</strong> You will
          not be able to deploy machines with this storage layout. Manual
          configuration is required.
        </p>
      )}
      {isVMWareLayout(values.default_storage_layout) && (
        <p
          className="p-form-validation__message"
          data-testid="vmfs6-layout-warning"
        >
          <i className="p-icon--warning" />
          <strong className="u-nudge-right--x-small">Caution:</strong> This
          storage layout only allows for the deployment of{" "}
          <strong>VMware (ESXi)</strong> images.
        </p>
      )}
      <FormikField
        help="Forces users to always erase disks when releasing."
        label="Erase nodes' disks prior to releasing"
        name="enable_disk_erasing_on_release"
        type="checkbox"
      />
      <FormikField
        help="Will only be used on devices that support secure erase. Other devices will fall back to full wipe or quick erase depending on the selected options."
        label="Use secure erase by default when erasing disks"
        name="disk_erase_with_secure_erase"
        type="checkbox"
      />
      <FormikField
        help="This is not a secure erase; it wipes only the beginning and end of each disk."
        label="Use quick erase by default when erasing disks"
        name="disk_erase_with_quick_erase"
        type="checkbox"
      />
    </>
  );
};

export default StorageFormFields;
