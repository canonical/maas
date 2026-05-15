import type { ReactNode } from "react";

import Popover from "@/app/base/components/Popover";
import type { KVMResource } from "@/app/kvm/types";
import { memoryWithUnit } from "@/app/kvm/utils";
import { resourceWithOverCommit } from "@/app/store/pod/utils";

type Props = {
  children: ReactNode;
  memory: {
    hugepages: KVMResource;
    general: KVMResource;
  };
  overCommit?: number;
};

const RAMPopover = ({
  children,
  memory,
  overCommit = 1,
}: Props): React.ReactElement => {
  const { general, hugepages } = memory;
  const hostGeneral =
    general.allocated_other + general.allocated_tracked + general.free;
  const hostHugepages =
    hugepages.allocated_other + hugepages.allocated_tracked + hugepages.free;
  const hostTotal = hostGeneral + hostHugepages;
  const generalOver = resourceWithOverCommit(general, overCommit);
  const allocated = generalOver.allocated_tracked + hugepages.allocated_tracked;
  const other = generalOver.allocated_other + hugepages.allocated_other;
  const free = generalOver.free + hugepages.free;
  const total = allocated + other + free;
  const showOther =
    general.allocated_other > 0 || hugepages.allocated_other > 0;
  const hasOverCommit = overCommit !== 1;

  return (
    <Popover
      className="ram-popover"
      content={
        <>
          <div className="ram-popover__header p-table__header">RAM</div>
          <div className="ram-popover__primary">
            <div className="u-align--right" data-testid="allocated">
              {`${memoryWithUnit(allocated)}`}
            </div>
            <div className="u-vertically-center">
              <i className="p-circle--link"></i>
            </div>
            <div>Allocated</div>
            {showOther && (
              <>
                <div className="u-align--right" data-testid="other">
                  {`${memoryWithUnit(other)}`}
                </div>
                <div className="u-vertically-center">
                  <i className="p-circle--positive"></i>
                </div>
                <div>Others</div>
              </>
            )}
            <div className="u-align--right" data-testid="free">
              {`${memoryWithUnit(free)}`}
            </div>
            <div className="u-vertically-center">
              <i className="p-circle--link-faded"></i>
            </div>
            <div>Free</div>
          </div>
          <div className="ram-popover__secondary">
            {hasOverCommit && (
              <>
                <div className="u-align--right" data-testid="host">
                  {`${memoryWithUnit(hostTotal)}`}
                </div>
                <div />
                <div>Host RAM</div>
                <div className="u-align--right">
                  &times;&nbsp;
                  <span data-testid="overcommit">{overCommit}</span>
                </div>
                <div />
                <div>Overcommit ratio</div>
                <hr className="ram-popover__separator" />
              </>
            )}
            <div className="u-align--right" data-testid="total">
              {`${memoryWithUnit(total)}`}
            </div>
            <div />
            <div>Total</div>
          </div>
        </>
      }
    >
      {children}
    </Popover>
  );
};

export default RAMPopover;
