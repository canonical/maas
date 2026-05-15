import pluralize from "pluralize";

import LabelledList from "@/app/base/components/LabelledList";
import Placeholder from "@/app/base/components/Placeholder";
import type { MachineDetails } from "@/app/store/machine/types";

type Props = {
  machine: MachineDetails | null;
};

export enum Labels {
  Title = "Source machine details",
  Status = "Status",
  Cpu = "CPU",
  Storage = "Storage",
  Memory = "Memory",
  PowerType = "Power type",
  Owner = "Owner",
  Host = "Host",
  Zone = "Zone",
  Domain = "Domain",
}

export const SourceMachineDetails = ({
  machine,
}: Props): React.ReactElement => {
  // Placeholder content is displayed until the machine has loaded.
  let content = {
    architecture: "Architecture",
    cores: "X cores, X.X GHz",
    cpuModel: "Model information",
    domain: "Domain",
    host: "Host name",
    memory: "X GiB",
    owner: "Owner",
    powerType: "Power type",
    status: "Machine status",
    storage: (
      <>
        X GB <small>over X disks</small>
      </>
    ),
    zone: "Zone name",
  };

  if (machine) {
    content = {
      architecture: machine.architecture,
      cores: `${pluralize("core", machine.cpu_count, true)}, ${
        machine.cpu_speed / 1000
      } GHz`,
      cpuModel: machine.metadata?.cpu_model || "Unknown model",
      domain: machine.domain?.name || "-",
      host: machine.pod?.name || "-",
      memory: `${machine.memory} GiB`,
      owner: machine.owner || "-",
      powerType: machine.power_type || "Unknown",
      status: machine.status,
      storage: (
        <>
          {machine.storage} GB{" "}
          <small>
            over {pluralize("disk", machine.physical_disk_count, true)}
          </small>
        </>
      ),
      zone: machine.zone?.name || "-",
    };
  }

  return (
    <LabelledList
      aria-label={Labels.Title}
      data-testid="source-machine-details"
      items={[
        {
          label: Labels.Status,
          value: <Placeholder loading={!machine}>{content.status}</Placeholder>,
        },
        {
          label: Labels.Cpu,
          value: (
            <>
              <Placeholder loading={!machine}>{content.cores}</Placeholder>
              <br />
              <Placeholder loading={!machine}>{content.cpuModel}</Placeholder>
              <br />
              <Placeholder loading={!machine}>
                {content.architecture}
              </Placeholder>
            </>
          ),
        },
        {
          label: Labels.Memory,
          value: <Placeholder loading={!machine}>{content.memory}</Placeholder>,
        },
        {
          label: Labels.Storage,
          value: (
            <Placeholder loading={!machine}>{content.storage}</Placeholder>
          ),
        },
        {
          label: Labels.PowerType,
          value: (
            <Placeholder loading={!machine}>{content.powerType}</Placeholder>
          ),
        },
        {
          label: Labels.Owner,
          value: <Placeholder loading={!machine}>{content.owner}</Placeholder>,
        },
        {
          label: Labels.Host,
          value: <Placeholder loading={!machine}>{content.host}</Placeholder>,
        },
        {
          label: Labels.Zone,
          value: <Placeholder loading={!machine}>{content.zone}</Placeholder>,
        },
        {
          label: Labels.Domain,
          value: <Placeholder loading={!machine}>{content.domain}</Placeholder>,
        },
      ]}
    />
  );
};

export default SourceMachineDetails;
