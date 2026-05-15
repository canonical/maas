import DoubleRow from "@/app/base/components/DoubleRow";
import MacAddressDisplay from "@/app/base/components/MacAddressDisplay";
import RowCheckbox from "@/app/base/components/RowCheckbox";
import type { Selected } from "@/app/base/components/node/networking/types";
import { useIsAllNetworkingDisabled } from "@/app/base/hooks";
import type {
  NetworkInterface,
  NetworkLink,
  Node,
} from "@/app/store/types/node";
import { getInterfaceName, getLinkInterface } from "@/app/store/utils";
import type { CheckboxHandlers } from "@/app/utils/generateCheckboxHandlers";

type Props = {
  checkboxSpace?: boolean;
  checkSelected?: CheckboxHandlers<Selected>["checkSelected"] | null;
  handleRowCheckbox?: CheckboxHandlers<Selected>["handleRowCheckbox"] | null;
  link?: NetworkLink | null;
  nic?: NetworkInterface | null;
  node: Node;
  selected?: Selected[] | null;
  showCheckbox?: boolean;
};

const NameColumn = ({
  checkboxSpace,
  checkSelected,
  handleRowCheckbox,
  link,
  nic,
  node,
  selected,
  showCheckbox,
}: Props): React.ReactElement | null => {
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(node);
  if (link && !nic) {
    [nic] = getLinkInterface(node, link);
  }
  if (!nic) {
    return null;
  }
  const name = getInterfaceName(node, nic, link);

  return (
    <DoubleRow
      primary={
        showCheckbox && handleRowCheckbox && selected ? (
          <RowCheckbox
            checkSelected={checkSelected}
            disabled={isAllNetworkingDisabled}
            handleRowCheckbox={handleRowCheckbox}
            inputLabel={<span data-testid="name">{name}</span>}
            item={{
              linkId: link?.id,
              nicId: nic.id,
            }}
            items={selected}
          />
        ) : (
          <span data-testid="name">{name}</span>
        )
      }
      primaryClassName={checkboxSpace ? "u-nudge--primary-row" : null}
      secondary={<MacAddressDisplay>{nic.mac_address}</MacAddressDisplay>}
      secondaryClassName={
        checkboxSpace || showCheckbox ? "u-nudge--secondary-row" : null
      }
    />
  );
};

export default NameColumn;
