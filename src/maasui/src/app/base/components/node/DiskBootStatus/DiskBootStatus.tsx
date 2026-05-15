import { Icon } from "@canonical/react-components";

import { DiskTypes } from "@/app/store/types/enum";
import type { Disk } from "@/app/store/types/node";

type Props = { disk: Disk };

const DiskBootStatus = ({ disk }: Props): React.ReactElement => {
  if (disk.type === DiskTypes.PHYSICAL) {
    return disk.is_boot ? (
      <Icon aria-label="Boot disk" name="tick" />
    ) : (
      <Icon aria-label="Non-boot disk" name="close" />
    );
  }
  return <span>—</span>;
};

export default DiskBootStatus;
