import { ExternalLink } from "@canonical/maas-react-components";
import { Icon } from "@canonical/react-components";

import TooltipButton from "@/app/base/components/TooltipButton";
import ControllerStatus from "@/app/controllers/components/ControllerStatus";
import type { Controller } from "@/app/store/controller/types";

type Props = {
  controller: Controller;
};

export const StatusColumn = ({
  controller,
}: Props): React.ReactElement | null => {
  // Map the issue id to the type of issue.
  const issues = (controller.versions?.issues || []).map((issue) =>
    issue.replace("different-", "")
  );
  const issue = issues.length
    ? `Different ${issues.join(" and ")} detected.`
    : null;

  return issue ? (
    <span data-testid="version-error">
      <Icon name="error" />{" "}
      <TooltipButton
        message={
          <>
            {issue}
            <br />
            <ExternalLink
              className="is-on-dark"
              to="https://discourse.maas.io/t/4555"
            >
              More info
            </ExternalLink>
          </>
        }
        position="top-center"
      />
    </span>
  ) : (
    <ControllerStatus controller={controller} />
  );
};

export default StatusColumn;
