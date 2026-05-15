import { Icon } from "@canonical/react-components";

import type { Service } from "@/app/store/service/types";
import { ServiceStatus as ServiceStatusType } from "@/app/store/service/types";
import { getServiceDisplayName } from "@/app/store/service/utils";

type Props = {
  service: Service;
};

const ServiceStatus = ({ service }: Props): React.ReactElement => {
  const iconName =
    service.status === ServiceStatusType.RUNNING
      ? "success"
      : service.status === ServiceStatusType.DEAD
        ? "error"
        : service.status === ServiceStatusType.DEGRADED
          ? "warning"
          : null;

  return (
    <span>
      {iconName && (
        <span className="u-nudge-left--small">
          <Icon
            aria-label={service.status}
            data-testid="service-status-icon"
            name={iconName}
          />
        </span>
      )}
      {getServiceDisplayName(service.name)}
      {service.status_info && (
        <small className="u-text--muted"> - {service.status_info}</small>
      )}
    </span>
  );
};

export default ServiceStatus;
