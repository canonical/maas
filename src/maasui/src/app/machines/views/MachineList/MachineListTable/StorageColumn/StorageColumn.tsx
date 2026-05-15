import { memo } from "react";

import { formatBytes } from "@canonical/maas-react-components";
import { useSelector } from "react-redux";

import DoubleRow from "@/app/base/components/DoubleRow";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine, MachineMeta } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  systemId: Machine[MachineMeta.PK];
};

export const StorageColumn = ({
  systemId,
}: Props): React.ReactElement | null => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  if (!machine) {
    return null;
  }
  const formattedStorage = formatBytes({ value: machine.storage, unit: "GB" });

  return (
    <DoubleRow
      primary={
        <>
          <span data-testid="storage-value">{formattedStorage.value}</span>
          &nbsp;
          <small className="u-text--light" data-testid="storage-unit">
            {formattedStorage.unit}
          </small>
        </>
      }
      primaryClassName="u-align--right"
    />
  );
};

export default memo(StorageColumn);
