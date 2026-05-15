import type { ReactNode } from "react";

import { Card, Icon, Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import ServiceStatus from "./ServiceStatus";

import { useFetchActions } from "@/app/base/hooks";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { RootState } from "@/app/store/root/types";
import { serviceActions } from "@/app/store/service";
import serviceSelectors from "@/app/store/service/selectors";
import type { Service } from "@/app/store/service/types";
import {
  ServiceName,
  ServiceStatus as ServiceStatusName,
} from "@/app/store/service/types";
import { NodeType } from "@/app/store/types/node";

type Props = {
  controller: ControllerDetails;
};

type ServiceItem = {
  children?: ServiceItem[];
  name: ServiceName;
  types: NodeType[];
};

const SERVICE_ITEMS: ServiceItem[] = [
  {
    name: ServiceName.REGIOND,
    types: [NodeType.REGION_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.BIND9,
    types: [NodeType.REGION_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.NTP_REGION,
    types: [NodeType.REGION_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.PROXY,
    types: [NodeType.REGION_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.SYSLOG_REGION,
    types: [NodeType.REGION_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.REVERSE_PROXY,
    types: [NodeType.REGION_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.TEMPORAL,
    types: [NodeType.REGION_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.RACKD,
    types: [NodeType.RACK_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
    children: [
      {
        name: ServiceName.HTTP,
        types: [NodeType.RACK_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
      },
      {
        name: ServiceName.TFTP,
        types: [NodeType.RACK_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
      },
      {
        name: ServiceName.AGENT,
        types: [NodeType.RACK_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
      },
    ],
  },
  {
    name: ServiceName.DHCPD,
    types: [NodeType.RACK_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.DHCPD6,
    types: [NodeType.RACK_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.DNS_RACK,
    types: [NodeType.RACK_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.NTP_RACK,
    types: [NodeType.RACK_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.PROXY_RACK,
    types: [NodeType.RACK_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
  {
    name: ServiceName.SYSLOG_RACK,
    types: [NodeType.RACK_CONTROLLER, NodeType.REGION_AND_RACK_CONTROLLER],
  },
];

const generateTree = (
  items: ServiceItem[],
  services: Service[],
  nodeType: NodeType
) => (
  <ul
    className="p-list-tree p-list-tree--static u-no-margin--bottom"
    role="tree"
  >
    {items.reduce<ReactNode[]>((acc, item) => {
      const service = services.find((service) => service.name === item.name);
      const includesType = item.types.includes(nodeType);
      if (service && includesType) {
        acc.push(
          <li className="p-list-tree__item" key={item.name}>
            <ServiceStatus service={service} />
            {item.children && generateTree(item.children, services, nodeType)}
          </li>
        );
      }
      return acc;
    }, [])}
  </ul>
);

const generateTitle = (services: Service[]) => {
  const { dead, degraded, running } = services.reduce(
    (acc, service) => {
      if (service.status === ServiceStatusName.DEAD) {
        acc.dead += 1;
      } else if (service.status === ServiceStatusName.DEGRADED) {
        acc.degraded += 1;
      } else if (service.status === ServiceStatusName.RUNNING) {
        acc.running += 1;
      }
      return acc;
    },
    { dead: 0, degraded: 0, running: 0 }
  );
  const substrings = [];
  let iconName = "";

  if (running > 0) {
    substrings.unshift(`${running} running`);
    iconName = "success";
  }
  if (degraded > 0) {
    substrings.unshift(`${degraded} degraded`);
    iconName = "warning";
  }
  if (dead > 0) {
    substrings.unshift(`${dead} dead`);
    iconName = "error";
  }

  return (
    <>
      <Icon aria-label={iconName} data-testid="title-icon" name={iconName} />
      <span className="u-nudge-right--small" data-testid="title">
        {substrings.join(", ")}
      </span>
    </>
  );
};

const ServicesCard = ({ controller }: Props): React.ReactElement => {
  const services = useSelector((state: RootState) =>
    serviceSelectors.getByIDs(state, controller.service_ids)
  );
  const servicesLoading = useSelector(serviceSelectors.loading);

  useFetchActions([serviceActions.fetch]);

  return (
    <Card>
      <strong className="p-muted-heading u-sv1">Services</strong>
      <hr />
      {servicesLoading ? (
        <Spinner aria-label="Loading services" text="Loading..." />
      ) : (
        <>
          <h4>{generateTitle(services)}</h4>
          {generateTree(SERVICE_ITEMS, services, controller.node_type)}
        </>
      )}
    </Card>
  );
};

export default ServicesCard;
