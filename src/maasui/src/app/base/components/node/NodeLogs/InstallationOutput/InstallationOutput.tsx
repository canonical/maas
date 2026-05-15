import { CodeSnippet, Spinner } from "@canonical/react-components";
import { CodeSnippetBlockAppearance } from "@canonical/react-components/dist/components/CodeSnippet";
import { useSelector } from "react-redux";

import { useGetInstallationOutput } from "../hooks";

import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import scriptResultSelectors from "@/app/store/scriptresult/selectors";
import { ScriptResultStatus } from "@/app/store/scriptresult/types";
import type {
  ScriptResult,
  ScriptResultData,
} from "@/app/store/scriptresult/types";
import { PowerState } from "@/app/store/types/enum";

type Props = {
  node: ControllerDetails | MachineDetails;
};

export enum Label {
  Aborted = "Installation was aborted.",
  Begun = "Installation has begun!",
  Booting = "System is booting...",
  Loading = "Loading installation output",
  None = "No installation result found.",
  SucceededNoOutput = "Installation has succeeded but no output was given.",
  FailedNoOutput = "Installation has failed and no output was given.",
  Off = "System is off.",
  Title = "Installation output",
  Timeout = "Installation failed after 40 minutes.",
}

const generateOutput = (
  node: Props["node"],
  log: ScriptResultData["combined"] | null,
  result: ScriptResult | null
) => {
  if (!result) {
    return Label.None;
  }
  switch (result.status) {
    case ScriptResultStatus.PENDING:
      if (node.power_state === PowerState.OFF) {
        return Label.Off;
      }
      return Label.Booting;
    case ScriptResultStatus.RUNNING:
      return Label.Begun;
    case ScriptResultStatus.PASSED:
      if (!log) {
        return Label.SucceededNoOutput;
      }
      return log;
    case ScriptResultStatus.FAILED:
      if (!log) {
        return Label.FailedNoOutput;
      }
      return log;
    case ScriptResultStatus.TIMEDOUT:
      return Label.Timeout;
    case ScriptResultStatus.ABORTED:
      return Label.Aborted;
    default:
      return `Unknown log status ${result.status}`;
  }
};

const InstallationOutput = ({ node }: Props): React.ReactElement => {
  const loading = useSelector((state: RootState) =>
    scriptResultSelectors.loading(state)
  );
  const installationOutput = useGetInstallationOutput(node.system_id);

  if (loading) {
    return <Spinner aria-label={Label.Loading} text="Loading..." />;
  }

  return (
    <CodeSnippet
      aria-label={Label.Title}
      blocks={[
        {
          appearance: CodeSnippetBlockAppearance.NUMBERED,
          code: generateOutput(
            node,
            installationOutput.log,
            installationOutput.result
          ),
        },
      ]}
    />
  );
};

export default InstallationOutput;
