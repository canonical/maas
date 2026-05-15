import type { ChipProps, PropsWithSpread } from "@canonical/react-components";
import { Chip } from "@canonical/react-components";

import type { TagIdCountMap } from "@/app/store/machine/utils";
import type { Tag } from "@/app/store/tag/types";

type Props = PropsWithSpread<
  {
    machineCount: number;
    tag: Tag;
    tagIdsAndCounts: TagIdCountMap | null;
  },
  Partial<ChipProps>
>;

export const TagChip = ({
  machineCount,
  tag,
  tagIdsAndCounts,
  ...props
}: Props): React.ReactElement => {
  const tagCount = tagIdsAndCounts?.get(tag.id);
  return (
    <Chip
      className="is-inline"
      key={tag.id}
      value={`${tag.name} (${tagCount}/${machineCount})`}
      {...props}
    />
  );
};

export default TagChip;
