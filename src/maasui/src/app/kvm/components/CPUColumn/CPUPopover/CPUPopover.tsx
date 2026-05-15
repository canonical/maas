import type { ReactNode } from "react";

import Popover from "@/app/base/components/Popover";
import type { KVMResource } from "@/app/kvm/types";
import { resourceWithOverCommit } from "@/app/store/pod/utils";

type Props = {
  children: ReactNode;
  cores: KVMResource;
  overCommit?: number;
};

const CPUPopover = ({
  children,
  cores,
  overCommit = 1,
}: Props): React.ReactElement => {
  const coresWithOver = resourceWithOverCommit(cores, overCommit);
  const hostCores =
    cores.allocated_other + cores.allocated_tracked + cores.free;
  const total =
    coresWithOver.allocated_other +
    coresWithOver.allocated_tracked +
    coresWithOver.free;
  const showOther = cores.allocated_other > 0;
  const hasOverCommit = overCommit !== 1;

  return (
    <Popover
      className="cpu-popover"
      content={
        <>
          <div className="cpu-popover__header p-table__header">CPU cores</div>
          <div className="cpu-popover__primary">
            <div className="u-align--right" data-testid="allocated">
              {coresWithOver.allocated_tracked}
            </div>
            <div className="u-vertically-center">
              <i className="p-circle--link"></i>
            </div>
            <div>Allocated</div>
            {showOther && (
              <>
                <div className="u-align--right" data-testid="other">
                  {coresWithOver.allocated_other}
                </div>
                <div className="u-vertically-center">
                  <i className="p-circle--positive"></i>
                </div>
                <div>Others</div>
              </>
            )}
            <div className="u-align--right" data-testid="free">
              {coresWithOver.free}
            </div>
            <div className="u-vertically-center">
              <i className="p-circle--link-faded"></i>
            </div>
            <div>Free</div>
          </div>
          <div className="cpu-popover__secondary">
            {hasOverCommit && (
              <>
                <div className="u-align--right" data-testid="host">
                  {hostCores}
                </div>
                <div />
                <div>{`Host core${hostCores === 1 ? "" : "s"}`}</div>
                <div className="u-align--right">
                  &times;&nbsp;
                  <span data-testid="overcommit">{overCommit}</span>
                </div>
                <div />
                <div>Overcommit ratio</div>
                <hr className="cpu-popover__separator" />
              </>
            )}
            <div className="u-align--right" data-testid="total">
              {total}
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

export default CPUPopover;
