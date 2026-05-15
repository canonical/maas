import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import { useFetchActions } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { spaceActions } from "@/app/store/space";
import spaceSelectors from "@/app/store/space/selectors";
import type { Space, SpaceMeta } from "@/app/store/space/types";
import { getSpaceDisplay } from "@/app/store/space/utils";

type Props = {
  id?: Space[SpaceMeta.PK] | null;
};

const SpaceLink = ({ id }: Props): React.ReactElement => {
  const space = useSelector((state: RootState) =>
    spaceSelectors.getById(state, id)
  );
  const spacesLoading = useSelector(spaceSelectors.loading);
  const spaceDisplay = getSpaceDisplay(space);

  useFetchActions([spaceActions.fetch]);

  if (spacesLoading) {
    return <Spinner aria-label="Loading spaces" />;
  }
  if (!space) {
    return <>{spaceDisplay}</>;
  }
  return (
    <Link to={urls.networks.space.index({ id: space.id })}>{spaceDisplay}</Link>
  );
};

export default SpaceLink;
