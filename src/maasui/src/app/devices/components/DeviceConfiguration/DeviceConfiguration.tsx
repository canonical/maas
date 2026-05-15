import { Spinner, Strip } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import { useZones } from "@/app/api/query/zones";
import Definition from "@/app/base/components/Definition";
import EditableSection from "@/app/base/components/EditableSection";
import FormikForm from "@/app/base/components/FormikForm";
import NodeConfigurationFields, {
  NodeConfigurationSchema,
} from "@/app/base/components/NodeConfigurationFields";
import type { NodeConfigurationValues } from "@/app/base/components/NodeConfigurationFields/types";
import TagLinks from "@/app/base/components/TagLinks";
import { useWindowTitle } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device, DeviceMeta } from "@/app/store/device/types";
import { FilterDevices, isDeviceDetails } from "@/app/store/device/utils";
import type { RootState } from "@/app/store/root/types";
import tagSelectors from "@/app/store/tag/selectors";

type Props = {
  systemId: Device[DeviceMeta.PK];
};

export enum Label {
  Title = "Device configuration",
  Form = "Device configuration form",
  Submit = "Save changes",
}

const DeviceConfiguration = ({ systemId }: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const device = useSelector((state: RootState) =>
    deviceSelectors.getById(state, systemId)
  );
  const updateDeviceError = useSelector((state: RootState) =>
    deviceSelectors.eventErrorsForDevices(state, systemId, "update")
  )[0]?.error;
  const deviceSaved = useSelector(deviceSelectors.saved);
  const deviceSaving = useSelector(deviceSelectors.saving);
  const deviceTags = useSelector((state: RootState) =>
    tagSelectors.getByIDs(state, device?.tags || null)
  );
  const zones = useZones();
  const loaded = isDeviceDetails(device) && !zones.isPending;
  useWindowTitle(`${`${device?.hostname}` || "Device"} configuration`);

  if (!loaded) {
    return (
      <Strip data-testid="loading-device" shallow>
        <Spinner text="Loading..." />
      </Strip>
    );
  }
  return (
    <EditableSection
      className="u-no-padding--top"
      hasSidebarTitle
      renderContent={(editing, setEditing) =>
        editing ? (
          <FormikForm<NodeConfigurationValues>
            aria-label={Label.Form}
            cleanup={deviceActions.cleanup}
            data-testid="device-config-form"
            editable={editing}
            errors={updateDeviceError}
            initialValues={{
              description: device.description,
              tags: device.tags,
              zone: device.zone?.name || "",
            }}
            onCancel={() => {
              setEditing(false);
            }}
            onSaveAnalytics={{
              action: "Configure device",
              category: "Device details",
              label: "Save changes",
            }}
            onSubmit={(values) => {
              const params = {
                description: values.description,
                system_id: device.system_id,
                tags: values.tags,
                zone: { name: values.zone },
              };
              dispatch(deviceActions.update(params));
            }}
            onSuccess={() => {
              setEditing(false);
            }}
            saved={deviceSaved}
            saving={deviceSaving}
            submitLabel={Label.Submit}
            validationSchema={NodeConfigurationSchema}
          >
            <NodeConfigurationFields />
          </FormikForm>
        ) : (
          <div data-testid="device-details">
            <Definition description={device.zone.name} label="Zone" />
            <Definition description={device.description} label="Note" />
            <Definition label="Tags">
              {device.tags.length ? (
                <TagLinks
                  getLinkURL={(tag) => {
                    const filter = FilterDevices.filtersToQueryString({
                      tags: [`=${tag.name}`],
                    });
                    return `${urls.devices.index}${filter}`;
                  }}
                  tags={deviceTags}
                />
              ) : null}
            </Definition>
          </div>
        )
      }
      title="Device configuration"
    />
  );
};

export default DeviceConfiguration;
