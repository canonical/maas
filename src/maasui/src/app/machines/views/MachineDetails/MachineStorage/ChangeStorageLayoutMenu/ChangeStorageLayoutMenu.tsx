import type { ReactElement } from "react";

import { ContextualMenu } from "@canonical/react-components";

import { useSidePanel } from "@/app/base/side-panel-context";
import ChangeStorageLayout from "@/app/machines/views/MachineDetails/MachineStorage/ChangeStorageLayout";
import type { Machine, StorageLayoutOption } from "@/app/store/machine/types";
import { StorageLayout } from "@/app/store/types/enum";

// TODO: Once the API returns a list of allowed storage layouts for a given
// machine we should either filter this list, or add a boolean e.g. "allowable"
// to each layout.
// https://github.com/canonical/maas-ui/issues/3258
export const storageLayoutOptions: StorageLayoutOption[][] = [
  [
    { label: "Flat", sentenceLabel: "flat", value: StorageLayout.FLAT },
    { label: "LVM", sentenceLabel: "LVM", value: StorageLayout.LVM },
    { label: "bcache", sentenceLabel: "bcache", value: StorageLayout.BCACHE },
    { label: "Custom", sentenceLabel: "custom", value: StorageLayout.CUSTOM },
  ],
  [
    {
      label: "VMFS6",
      sentenceLabel: "VMFS6",
      value: StorageLayout.VMFS6,
    },
    {
      label: "VMFS7",
      sentenceLabel: "VMFS7",
      value: StorageLayout.VMFS7,
    },
  ],
  [
    {
      label: "No storage (blank) layout",
      sentenceLabel: "blank",
      value: StorageLayout.BLANK,
    },
  ],
];

type ChangeStorageLayoutMenuProps = {
  systemId: Machine["system_id"];
};

const ChangeStorageLayoutMenu = ({
  systemId,
}: ChangeStorageLayoutMenuProps): ReactElement => {
  const { openSidePanel } = useSidePanel();
  return (
    <div className="u-align--right">
      <ContextualMenu
        hasToggleIcon
        links={storageLayoutOptions.map((group) =>
          group.map((option) => ({
            children: option.label,
            onClick: () => {
              openSidePanel({
                component: ChangeStorageLayout,
                title: "Change storage layout",
                props: {
                  systemId,
                  selectedLayout: option,
                },
              });
            },
          }))
        )}
        position="right"
        toggleLabel="Change storage layout"
      />
    </div>
  );
};

export default ChangeStorageLayoutMenu;
