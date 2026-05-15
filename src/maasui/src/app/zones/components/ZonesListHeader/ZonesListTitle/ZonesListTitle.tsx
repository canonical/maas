import TooltipButton from "@/app/base/components/TooltipButton";

const ZonesListTitle = (): React.ReactElement => {
  return (
    <>
      Availability zones
      <TooltipButton
        aria-label="About availability zones"
        buttonProps={{ className: "u-no-border u-no-margin u-match-h3" }}
        className="u-nudge-right--small"
        iconName="help"
        message="A representation of a grouping of nodes, typically by physical location."
      />
    </>
  );
};

export default ZonesListTitle;
