import type { ChangeEvent } from "react";

import {
  Col,
  Notification as NotificationBanner,
  Row,
  Select,
} from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { ConfigureDHCPValues } from "../ConfigureDHCP";
import { DHCPType } from "../ConfigureDHCP";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import VLANSelect from "@/app/base/components/VLANSelect";
import controllerSelectors from "@/app/store/controller/selectors";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { RootState } from "@/app/store/root/types";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";
import { getFullVLANName } from "@/app/store/vlan/utils";
import { simpleSortByKey } from "@/app/utils";

type Props = {
  vlan: VLAN;
};

const ConfigureDHCPFields = ({ vlan }: Props): React.ReactElement => {
  const {
    handleChange,
    setFieldValue,
    values: { dhcpType, enableDHCP, primaryRack, secondaryRack },
  } = useFormikContext<ConfigureDHCPValues>();
  const fabrics = useSelector(fabricSelectors.all);
  const allVLANs = useSelector(vlanSelectors.all);
  const vlansWithDHCP = useSelector(vlanSelectors.getWithDHCP).filter(
    (dhcpVLAN) => dhcpVLAN.id !== vlan.id
  );
  const connectedControllers = useSelector((state: RootState) =>
    controllerSelectors.getByIDs(state, vlan.rack_sids)
  );
  const primaryRackOptions = connectedControllers.filter(
    (controller) => controller.system_id !== secondaryRack
  );
  const secondaryRackOptions = connectedControllers.filter(
    (controller) => controller.system_id !== primaryRack
  );

  return (
    <Row>
      <Col size={12}>
        <FormikField
          label="MAAS provides DHCP"
          name="enableDHCP"
          type="checkbox"
        />
        {enableDHCP && (
          <>
            <FormikField
              label="Provide DHCP from rack controller(s)"
              name="dhcpType"
              onChange={async (e: ChangeEvent) => {
                // eslint-disable-next-line @typescript-eslint/no-confusing-void-expression
                await handleChange(e);
                setFieldValue(
                  "primaryRack",
                  connectedControllers[0]?.system_id || ""
                ).catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "primaryRack",
                    "setFieldValue",
                    reason as string
                  );
                });
                setFieldValue("relayVLAN", "").catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "relayVLAN",
                    "setFieldValue",
                    reason as string
                  );
                });
              }}
              type="radio"
              value={DHCPType.CONTROLLERS}
            />
            {dhcpType === DHCPType.CONTROLLERS && (
              <>
                {connectedControllers.length === 0 ? (
                  <NotificationBanner severity="negative">
                    This VLAN is not currently being utilised on any rack
                    controller.
                  </NotificationBanner>
                ) : (
                  <>
                    <FormikField
                      component={Select}
                      label={
                        connectedControllers.length === 1
                          ? "Rack controller"
                          : "Primary rack"
                      }
                      name="primaryRack"
                      options={[
                        { label: "Select rack controller", value: "" },
                        ...primaryRackOptions
                          .map((controller) => ({
                            label: controller.hostname,
                            value: controller.system_id,
                          }))
                          .sort(
                            simpleSortByKey("label", { alphanumeric: true })
                          ),
                      ]}
                      required
                      wrapperClassName="u-nudge-right--x-large"
                    />
                    {connectedControllers.length > 1 && (
                      <FormikField
                        component={Select}
                        label="Secondary rack"
                        name="secondaryRack"
                        options={[
                          { label: "Unset", value: "" },
                          ...secondaryRackOptions
                            .map((controller) => ({
                              label: controller.hostname,
                              value: controller.system_id,
                            }))
                            .sort(
                              simpleSortByKey("label", { alphanumeric: true })
                            ),
                        ]}
                        wrapperClassName="u-nudge-right--x-large"
                      />
                    )}
                  </>
                )}
              </>
            )}
            <FormikField
              label="Relay to another VLAN"
              name="dhcpType"
              onChange={async (e: ChangeEvent) => {
                // eslint-disable-next-line @typescript-eslint/no-confusing-void-expression
                await handleChange(e);
                setFieldValue("relayVLAN", vlansWithDHCP[0]?.id || "").catch(
                  (reason: unknown) => {
                    throw new FormikFieldChangeError(
                      "relayVLAN",
                      "setFieldValue",
                      reason as string
                    );
                  }
                );
                setFieldValue("primaryRack", "").catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "primaryRack",
                    "setFieldValue",
                    reason as string
                  );
                });
                setFieldValue("secondaryRack", "").catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    "secondaryRack",
                    "setFieldValue",
                    reason as string
                  );
                });
              }}
              type="radio"
              value={DHCPType.RELAY}
            />
            {dhcpType === DHCPType.RELAY && (
              <VLANSelect
                defaultOption={null}
                generateName={(dhcpVLAN) =>
                  getFullVLANName(dhcpVLAN.id, allVLANs, fabrics) ||
                  dhcpVLAN.name
                }
                label="VLAN"
                name="relayVLAN"
                vlans={vlansWithDHCP}
                wrapperClassName="u-nudge-right--x-large"
              />
            )}
          </>
        )}
      </Col>
      {!enableDHCP && (
        <NotificationBanner severity="caution">
          Are you sure you want to disable DHCP on this VLAN? All subnets on
          this VLAN will be affected.
        </NotificationBanner>
      )}
    </Row>
  );
};

export default ConfigureDHCPFields;
