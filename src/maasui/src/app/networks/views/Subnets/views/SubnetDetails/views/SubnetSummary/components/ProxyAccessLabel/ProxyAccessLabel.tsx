import TooltipButton from "@/app/base/components/TooltipButton";
import type { Subnet } from "@/app/store/subnet/types";

type Props = {
  allowProxy: Subnet["allow_proxy"];
};

const ProxyAccessLabel = ({ allowProxy }: Props): React.ReactElement => (
  <>
    Proxy access{" "}
    <TooltipButton
      aria-label="More about proxy access"
      message={`MAAS will ${
        allowProxy ? "" : "not"
      } allow clients from this subnet to access the MAAS proxy.`}
      position="btm-right"
      positionElementClassName="u-display--inline"
    />
  </>
);

export default ProxyAccessLabel;
