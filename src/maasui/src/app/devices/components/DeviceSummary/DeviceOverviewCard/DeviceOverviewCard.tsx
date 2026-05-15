import { Card, Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import LabelledList from "@/app/base/components/LabelledList";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device, DeviceMeta } from "@/app/store/device/types";
import { isDeviceDetails } from "@/app/store/device/utils";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";
import { getTagsDisplay } from "@/app/store/tag/utils";

type Props = {
  systemId: Device[DeviceMeta.PK];
};

const DeviceOverviewCard = ({ systemId }: Props): React.ReactElement | null => {
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, systemId)
  );
  const tagsLoaded = useSelector(tagSelectors.loaded);
  const deviceTags = useSelector((state: RootState) =>
    tagSelectors.getByIDs(state, device?.tags || null)
  );

  if (!device) {
    return null;
  }

  const tagDisplay = getTagsDisplay(deviceTags);
  const {
    domain: { name: domainName },
    owner,
    zone: { name: zoneName },
  } = device;
  return (
    <Card>
      <h4 className="p-muted-heading u-sv1">Overview</h4>
      <hr />
      <LabelledList
        className="u-no-margin--bottom"
        items={[
          {
            label: "Owner",
            value: owner || "—",
          },
          {
            label: "Domain",
            value: domainName || "—",
          },
          {
            label: "Zone",
            value: zoneName || "—",
          },
          {
            label: "Note",
            value: isDeviceDetails(device) ? (
              <span data-testid="device-note">{device.description || "—"}</span>
            ) : (
              <Spinner data-testid="loading-note" />
            ),
          },
          {
            label: "Tags",
            value: tagsLoaded ? (
              <span data-testid="device-tags">{tagDisplay}</span>
            ) : (
              <Spinner data-testid="loading-tags" />
            ),
          },
        ]}
      />
    </Card>
  );
};

export default DeviceOverviewCard;
