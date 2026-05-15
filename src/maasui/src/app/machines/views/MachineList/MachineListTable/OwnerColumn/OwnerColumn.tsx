import { memo, useCallback, useEffect, useMemo, useState } from "react";

import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import { useUsers } from "@/app/api/query/users";
import DoubleRow from "@/app/base/components/DoubleRow";
import { useMachineActions } from "@/app/base/hooks";
import type { MachineMenuAction } from "@/app/base/hooks/node";
import { useToggleMenu } from "@/app/machines/hooks";
import type { MachineMenuToggleHandler } from "@/app/machines/types";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine, MachineMeta } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";
import { getTagsDisplay } from "@/app/store/tag/utils";
import { NodeActions } from "@/app/store/types/node";

type Props = {
  onToggleMenu?: MachineMenuToggleHandler;
  systemId: Machine[MachineMeta.PK];
  showFullName?: boolean;
};

const actions: MachineMenuAction[] = [NodeActions.ACQUIRE, NodeActions.RELEASE];

export const OwnerColumn = ({
  onToggleMenu,
  systemId,
  showFullName,
}: Props): React.ReactElement => {
  const [updating, setUpdating] = useState<Machine["status"] | null>(null);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const machineTags = useSelector((state: RootState) =>
    tagSelectors.getByIDs(state, machine?.tags || null)
  );
  const toggleMenu = useToggleMenu(onToggleMenu || null);
  const user =
    useUsers({ query: { username_or_email: machine?.owner || "" } }).data
      ?.items[0] || null;
  const ownerDisplay = showFullName
    ? user?.last_name || machine?.owner || "-"
    : machine?.owner || "-";
  const tagsDisplay = getTagsDisplay(machineTags);

  const handleMachineActionClick = useCallback(() => {
    if (machine) {
      setUpdating(machine.status);
    }
  }, [machine]);

  const menuLinks = useMachineActions(
    systemId,
    actions,
    "No owner actions available",
    handleMachineActionClick
  );

  useEffect(() => {
    if (updating !== null && machine?.status !== updating) {
      setUpdating(null);
    }
  }, [updating, machine?.status]);

  const primary = useMemo(
    () => (
      <>
        {updating === null ? null : <Spinner className="u-nudge-left--small" />}
        <span data-testid="owner">{ownerDisplay}</span>
      </>
    ),
    [updating, ownerDisplay]
  );
  const secondary = useMemo(
    () => (
      <span data-testid="tags" title={tagsDisplay}>
        {tagsDisplay}
      </span>
    ),
    [tagsDisplay]
  );

  return (
    <DoubleRow
      menuLinks={onToggleMenu ? menuLinks : null}
      menuTitle="Take action:"
      onToggleMenu={toggleMenu}
      primary={primary}
      primaryTitle={ownerDisplay}
      secondary={secondary}
      secondaryTitle={tagsDisplay}
    />
  );
};

export default memo(OwnerColumn);
