import { Icon } from "@canonical/react-components";
import { Link, useLocation } from "react-router";

type LocationState = {
  from?: string;
};

const SettingsBackLink = (): React.ReactElement | null => {
  const location = useLocation();
  const state = location.state as LocationState;
  if (!state?.from) {
    return null;
  }

  return (
    <div className="settings-back-link">
      <Link className="settings-back-link__link" to={state.from}>
        <Icon className="u-rotate-right u-no-margin--left" name="chevron-up" />
        <span>Back</span>
      </Link>
      <hr className="settings-back-link__divider" />
    </div>
  );
};

export default SettingsBackLink;
