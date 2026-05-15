import { Button, Tooltip } from "@canonical/react-components";

import type { Selected } from "@/app/base/components/node/networking/types";
import { useSendAnalytics } from "@/app/base/hooks";
import type { NetworkInterface } from "@/app/store/types/node";

type Props = {
  editingMembers?: boolean;
  selected: Selected[];
  setEditingMembers: (editingMembers: boolean) => void;
  validNics: NetworkInterface[];
};

export const ToggleMembers = ({
  editingMembers = false,
  selected,
  setEditingMembers,
  validNics,
}: Props): React.ReactElement => {
  const sendAnalytics = useSendAnalytics();
  let editTooltip: string | null = null;
  let editDisabled = false;
  if (!editingMembers && validNics.length === 2) {
    // Disable the button to add more members if there are no more to choose
    // from.
    editTooltip = "There are no additional valid members";
    editDisabled = true;
  } else if (editingMembers && selected.length < 2) {
    // Don't let the user update the selection if they haven't chosen at least
    // two interfaces.
    editTooltip = "At least two interfaces must be selected";
    editDisabled = true;
  }
  return (
    <Tooltip message={editTooltip}>
      <Button
        data-testid="edit-members"
        disabled={editDisabled}
        onClick={() => {
          sendAnalytics(
            "Machine details networking",
            "Bond form",
            editingMembers ? "Update bond members" : "Edit bond members"
          );
          setEditingMembers(!editingMembers);
        }}
        type="button"
      >
        {editingMembers ? "Update bond members" : "Edit bond members"}
      </Button>
    </Tooltip>
  );
};

export default ToggleMembers;
