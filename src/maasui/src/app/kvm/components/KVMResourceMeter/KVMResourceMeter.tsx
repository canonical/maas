import { Meter, formatBytes } from "@canonical/maas-react-components";

import { COLOURS } from "@/app/base/constants";

type Props = {
  allocated: number;
  binaryUnit?: boolean;
  detailed?: boolean;
  free: number;
  other?: number;
  segmented?: boolean;
  unit?: string | null;
};

const KVMResourceMeter = ({
  allocated,
  binaryUnit = false,
  detailed = false,
  free,
  other = 0,
  segmented = false,
  unit = null,
}: Props): React.ReactElement | null => {
  const total = allocated + free + other;
  const { value: formattedTotal, unit: formattedUnit } = unit
    ? formatBytes({ value: total, unit }, { binary: binaryUnit, decimals: 1 })
    : { value: Number(total.toFixed(1)), unit: "" };
  const formatResource = (resource: number) =>
    unit
      ? formatBytes(
          { value: resource, unit },
          {
            binary: binaryUnit,
            convertTo: formattedUnit,
            decimals: 1,
          }
        ).value
      : Number(resource.toFixed(1));
  const formattedAllocated = formatResource(allocated);
  const formattedFree = formatResource(free);
  const formattedOther = formatResource(other);

  return (
    <div className="kvm-resource-meter">
      {detailed && (
        <div className="u-flex--between" data-testid="kvm-resource-details">
          <div className="u-flex--grow u-nudge-left--small u-align-text--left">
            <div className="p-text--x-small-capitalised u-text--muted u-sv-1">
              Allocated
              <span className="u-nudge-right--small">
                <i className="p-circle--link u-no-margin--top"></i>
              </span>
            </div>
            <span data-testid="kvm-resource-allocated">
              {`${formattedAllocated}${formattedUnit}`}
            </span>
          </div>
          {formattedOther > 0 && (
            <div className="u-flex--grow u-nudge-left--small">
              <div className="p-text--x-small-capitalised u-text--muted u-sv-1">
                Others
                <span className="u-nudge-right--small">
                  <i className="p-circle--positive u-no-margin--top"></i>
                </span>
              </div>
              <span data-testid="kvm-resource-other">
                {`${formattedOther}${formattedUnit}`}
              </span>
            </div>
          )}
          <div className="u-flex--no-shrink">
            <div className="p-text--x-small-capitalised u-text--muted u-align--right u-sv-1">
              Free
              <span className="u-nudge-right--small">
                <i className="p-circle--link-faded u-no-margin--top"></i>
              </span>
            </div>
            <span data-testid="kvm-resource-free">
              {`${formattedFree}${formattedUnit}`}
            </span>
          </div>
        </div>
      )}
      <Meter
        className="u-flex--column-align-end u-no-margin--bottom"
        data={[
          {
            color: COLOURS.LINK,
            value: allocated,
          },
          {
            color: COLOURS.POSITIVE,
            value: other,
          },
          {
            color: COLOURS.LINK_FADED,
            value: free > 0 ? free : 0,
          },
        ]}
        max={total}
        size="small"
        variant={segmented ? "segmented" : "regular"}
      >
        <Meter.Label className="u-align--right">
          {detailed ? (
            <div>
              <div className="p-text--x-small-capitalised u-text--muted u-sv-1">
                Total
              </div>
              <div className="u-align--left">{`${formattedTotal}${formattedUnit}`}</div>
            </div>
          ) : (
            <small
              className="u-text--muted u-no-margin--bottom"
              data-testid="kvm-resource-summary"
            >
              {`${formattedAllocated} of ${formattedTotal}${formattedUnit} allocated`}
            </small>
          )}
        </Meter.Label>
      </Meter>
    </div>
  );
};

export default KVMResourceMeter;
