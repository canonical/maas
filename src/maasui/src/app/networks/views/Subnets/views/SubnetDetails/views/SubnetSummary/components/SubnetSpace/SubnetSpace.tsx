import Definition from "@/app/base/components/Definition";
import SpaceLink from "@/app/base/components/SpaceLink";
import TooltipButton from "@/app/base/components/TooltipButton";
import type { Space, SpaceMeta } from "@/app/store/space/types";
import { isId } from "@/app/utils";

type Props = {
  spaceId?: Space[SpaceMeta.PK] | null;
};

const SubnetSpace = ({ spaceId }: Props): React.ReactElement | null => {
  return (
    <Definition label="Space">
      <>
        <SpaceLink id={spaceId} />{" "}
        {isId(spaceId) ? null : (
          <TooltipButton
            iconName="warning"
            message={`This subnet does not belong to a space. MAAS integrations
            require a space in order to determine the purpose of a network.`}
            position="btm-right"
          />
        )}
      </>
    </Definition>
  );
};

export default SubnetSpace;
