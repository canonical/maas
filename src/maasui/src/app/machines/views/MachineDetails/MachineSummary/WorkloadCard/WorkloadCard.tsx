import { ExternalLink } from "@canonical/maas-react-components";
import { Card, Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link as RouterLink } from "react-router";

import LabelledList from "@/app/base/components/LabelledList";
import TooltipButton from "@/app/base/components/TooltipButton";
import { useSendAnalytics } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import { FilterMachines, isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  id: Machine["system_id"];
};

const WorkloadCard = ({ id }: Props): React.ReactElement => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  const sendAnalytics = useSendAnalytics();
  let content: React.ReactElement;

  if (isMachineDetails(machine)) {
    const workloads = Object.entries(machine.workload_annotations || {}).sort(
      (a, b) => a[0].localeCompare(b[0])
    );

    if (workloads.length > 0) {
      content = (
        <LabelledList
          className="u-no-margin--bottom"
          data-testid="workload-annotations"
          items={workloads.map(([key, value]) => {
            const separatedValue = value.split(",");
            return {
              label: <div data-testid="workload-key">{key}</div>,
              value: (
                <div data-testid="workload-value" key={key}>
                  {separatedValue.map((val) => {
                    const filter = FilterMachines.filtersToQueryString({
                      [`workload-${key}`]: [`${val}`],
                    });
                    return (
                      <div key={`${key}-${val}`}>
                        <RouterLink to={`${urls.machines.index}${filter}`}>
                          {val}
                        </RouterLink>
                      </div>
                    );
                  })}
                </div>
              ),
            };
          })}
        />
      );
    } else {
      content = (
        <div data-testid="no-workload-annotations">
          <h4>No workload information</h4>
        </div>
      );
    }
  } else {
    content = <Spinner />;
  }

  return (
    <div className="machine-summary__workload-card">
      <Card>
        <div className="u-flex--between">
          <div className="u-sv1">
            <strong className="p-muted-heading">Workload annotations</strong>
            <span className="u-nudge-right--small">
              <TooltipButton
                iconName="help"
                message="MAAS removes workload annotations when the machine is released."
                position="top-center"
              />
            </span>
          </div>
          <ExternalLink
            onClick={() => {
              sendAnalytics(
                "Machine summary",
                "Click link to workload annotation docs",
                "Read more"
              );
            }}
            to="https://discourse.maas.io/t/machine-workload-annotations/4237"
          >
            Read more
          </ExternalLink>
        </div>
        <hr />
        {content}
      </Card>
    </div>
  );
};

export default WorkloadCard;
