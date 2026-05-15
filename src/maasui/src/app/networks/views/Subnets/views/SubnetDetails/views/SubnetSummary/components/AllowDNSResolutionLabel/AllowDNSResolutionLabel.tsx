import TooltipButton from "@/app/base/components/TooltipButton";
import type { Subnet } from "@/app/store/subnet/types";

type Props = {
  allowDNS: Subnet["allow_dns"];
};

const AllowDNSResolutionLabel = ({ allowDNS }: Props): React.ReactElement => (
  <>
    Allow DNS resolution{" "}
    <TooltipButton
      message={`MAAS will ${
        allowDNS ? "" : "not"
      } allow clients from this subnet to use MAAS for DNS resolution.`}
      position="btm-right"
      positionElementClassName="u-display--inline"
    />
  </>
);

export default AllowDNSResolutionLabel;
