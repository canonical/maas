import { Col, Row, Select } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import type { DiscoveryAddValues } from "../types";
import { DeviceType } from "../types";

import type { DiscoveryResponse } from "@/app/apiclient";
import MachineSelect from "@/app/base/components/DhcpFormFields/MachineSelect";
import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import IpAssignmentSelect from "@/app/base/components/IpAssignmentSelect";
import TooltipButton from "@/app/base/components/TooltipButton";
import urls from "@/app/base/urls";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device } from "@/app/store/device/types";
import { DeviceMeta } from "@/app/store/device/types";
import domainSelectors from "@/app/store/domain/selectors";
import type { RootState } from "@/app/store/root/types";
import subnetSelectors from "@/app/store/subnet/selectors";
import { getSubnetDisplay } from "@/app/store/subnet/utils";
import { FetchNodeStatus } from "@/app/store/types/node";
import vlanSelectors from "@/app/store/vlan/selectors";
import { getVLANDisplay } from "@/app/store/vlan/utils";

type Props = {
  discovery: DiscoveryResponse;
  setDevice: (device: Device[DeviceMeta.PK] | null) => void;
  setDeviceType: (deviceType: DeviceType) => void;
};

export enum Labels {
  ChooseType = "Choose type",
  ChooseDomain = "Choose domain",
  Type = "Type",
  Device = "Device",
  DeviceName = "Device Name",
  Interface = "Interface",
  Parent = "Parent",
  Hostname = "Hostname (optional)",
  InterfaceName = "Interface name (optional)",
  Domain = "Domain",
  SelectDeviceName = "Select device name",
  SelectParent = "Select parent (optional)",
  Fabric = "Fabric",
  Vlan = "VLAN",
  Subnet = "Subnet",
}

const DiscoveryAddFormFields = ({
  discovery,
  setDevice,
  setDeviceType,
}: Props): React.ReactElement | null => {
  const devices = useSelector(deviceSelectors.all);
  const domains = useSelector(domainSelectors.all);
  const subnet = useSelector((state: RootState) =>
    subnetSelectors.getByCIDR(state, discovery.subnet_cidr!)
  );
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, discovery.vlan_id)
  );
  const { setFieldValue, values } = useFormikContext<DiscoveryAddValues>();
  const isDevice = values.type === DeviceType.DEVICE;
  const isInterface = values.type === DeviceType.INTERFACE;
  // Only include static when the discovery has a subnet.
  const includeStatic = !!discovery.subnet_id || discovery.subnet_id === 0;
  const subnetDisplay = getSubnetDisplay(subnet);
  const vlanDisplay = getVLANDisplay(vlan);

  return (
    <>
      <Row>
        <Col size={12}>
          <FormikField
            component={Select}
            label={Labels.Type}
            name="type"
            onChange={(evt: React.ChangeEvent<HTMLSelectElement>) => {
              setFieldValue("type", evt.target.value).catch(
                (reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "type",
                    "setFieldValue",
                    reason as string
                  );
                }
              );
              setDeviceType(evt.target.value as DeviceType);
              // Clear the device in case it has been set previously.
              setDevice(null);
            }}
            options={[
              { label: Labels.ChooseType, value: "", disabled: true },
              { label: Labels.Device, value: DeviceType.DEVICE },
              { label: Labels.Interface, value: DeviceType.INTERFACE },
            ]}
            required
          />
          <FormikField
            label={isDevice ? Labels.Hostname : Labels.InterfaceName}
            name="hostname"
            type="text"
          />
          {isDevice ? (
            <FormikField
              component={Select}
              label={Labels.Domain}
              name="domain"
              options={[
                { label: Labels.ChooseDomain, value: "", disabled: true },
                ...domains.map((domain) => ({
                  label: domain.name,
                  value: domain.name,
                })),
              ]}
              required
            />
          ) : null}
          {isInterface ? (
            <FormikField
              aria-label={Labels.DeviceName}
              component={Select}
              label={
                <>
                  {Labels.DeviceName}{" "}
                  <TooltipButton message="Create as an interface on the selected device." />
                </>
              }
              name={DeviceMeta.PK}
              onChange={(evt: React.ChangeEvent<HTMLSelectElement>) => {
                setFieldValue(DeviceMeta.PK, evt.target.value).catch(
                  (reason: unknown) => {
                    throw new FormikFieldChangeError(
                      DeviceMeta.PK,
                      "setFieldValue",
                      reason as string
                    );
                  }
                );
                setDevice(evt.target.value);
              }}
              options={[
                { label: Labels.SelectDeviceName, value: "", disabled: true },
                ...devices.map((device) => ({
                  label: device.fqdn,
                  value: device[DeviceMeta.PK],
                })),
              ]}
              required
            />
          ) : (
            <FormikField
              component={MachineSelect}
              defaultOption={Labels.SelectParent}
              filters={{ status: FetchNodeStatus.DEPLOYED }}
              label={
                <>
                  {Labels.Parent}{" "}
                  <TooltipButton message="Assign this device as a child of the parent machine." />
                </>
              }
              name="parent"
            />
          )}
        </Col>
        <Col size={12}>
          <IpAssignmentSelect
            includeStatic={includeStatic}
            name="ip_assignment"
            required
          />
          <div className="">
            <p>{Labels.Fabric}</p>
            <p>
              <Link
                to={urls.networks.fabric.index({ id: discovery.fabric_id! })}
              >
                {discovery.fabric_name}
              </Link>
            </p>
          </div>
          <div className="u-nudge-down--small">
            <p>{Labels.Vlan}</p>
            <p>
              {vlanDisplay ? (
                <Link to={urls.networks.vlan.index({ id: discovery.vlan_id! })}>
                  {vlanDisplay}
                </Link>
              ) : null}
            </p>
          </div>
          <div className="u-nudge-down--small">
            <p>{Labels.Subnet}</p>
            {discovery.subnet_id && subnetDisplay ? (
              <p>
                <Link
                  to={urls.networks.subnet.index({ id: discovery.subnet_id })}
                >
                  {subnetDisplay}
                </Link>
              </p>
            ) : null}
          </div>
        </Col>
      </Row>
    </>
  );
};

export default DiscoveryAddFormFields;
