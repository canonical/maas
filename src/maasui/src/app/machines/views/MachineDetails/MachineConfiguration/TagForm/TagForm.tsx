import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import EditableSection from "@/app/base/components/EditableSection";
import TagLinks from "@/app/base/components/TagLinks";
import { useFetchActions, useCanEdit } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import TagActionForm from "@/app/machines/components/MachineForms/MachineActionFormWrapper/TagForm";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";

type Props = { systemId: MachineDetails["system_id"] };

const TagForm = ({ systemId }: Props): React.ReactElement | null => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const tags = useSelector((state: RootState) =>
    tagSelectors.getByIDs(state, machine?.tags || null)
  );
  const tagsLoading = useSelector(tagSelectors.loading);

  const canEdit = useCanEdit(machine, true);

  useFetchActions([tagActions.fetch]);

  if (!machine || tagsLoading) {
    return <Spinner text="Loading..." />;
  }

  return (
    <EditableSection
      canEdit={canEdit}
      hasSidebarTitle
      renderContent={(editing, setEditing) =>
        editing ? (
          <TagActionForm
            closeForm={() => {
              setEditing(false);
            }}
            isViewingDetails
            isViewingMachineConfig
          />
        ) : (
          <p>
            <TagLinks
              getLinkURL={(tag) => {
                const filter = FilterMachines.filtersToQueryString({
                  tags: [`=${tag.name}`],
                });
                return `${urls.machines.index}${filter}`;
              }}
              tags={tags}
            />
          </p>
        )
      }
      title="Tags"
    />
  );
};

export default TagForm;
