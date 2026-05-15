import * as React from "react";

import {
  Button,
  Card,
  Col,
  Row,
  Select,
  Tooltip,
} from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { ComposeFormValues, InterfaceField } from "../ComposeForm";

import SubnetSelect from "./SubnetSelect";

import Definition from "@/app/base/components/Definition";
import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import fabricSelectors from "@/app/store/fabric/selectors";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod, PodDetails } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import spaceSelectors from "@/app/store/space/selectors";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";

/**
 * Generate a new InterfaceField with a given id and preselected subnet.
 * @param id - The id to give the new InterfaceField.
 * @param subnetId - The id of the subnet that the new interface should belong to.
 * @returns Generated InterfaceField.
 */
const generateNewInterface = (
  id: number,
  subnetId?: Subnet["id"]
): InterfaceField => {
  return {
    id,
    ipAddress: "",
    name: `eth${id}`,
    space: "",
    subnet: `${subnetId || ""}`,
  };
};

/**
 * Get the icon props for the interface's PXE.
 * @param pod - The pod whose boot VLANs are to be checked.
 * @param vlan - The VLAN of the interface's selected subnet.
 * @returns The props of the PXE icon.
 */
export const getPxeIconProps = (
  pod?: PodDetails,
  vlan?: VLAN
): { "aria-label": string; className: string } => {
  if (!vlan || !pod) {
    return { "aria-label": "-", className: "p-icon--minus" };
  }
  return pod.boot_vlans?.includes(vlan.id)
    ? { "aria-label": "success", className: "p-icon--success" }
    : { "aria-label": "error", className: "p-icon--error" };
};

/**
 * Generate tooltip message for disabled "Define" interfaces button.
 * @param hasSubnets - Whether the pod has any subnets on its attached VLANs.
 * @param hasPxeSubnets - Whether the pod has any subnets on its boot VLANs.
 * @returns Tooltip message for disabled button.
 */
const getTooltipMessage = (hasSubnets: boolean, hasPxeSubnets: boolean) => {
  if (!hasSubnets) {
    return "There are no available networks seen by this KVM host.";
  }
  if (!hasPxeSubnets) {
    return "There are no PXE-enabled networks seen by this KVM host.";
  }
  return null;
};

type Props = {
  hostId: Pod["id"];
};

export const InterfacesTable = ({ hostId }: Props): React.ReactElement => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  ) as PodDetails;
  const allPodSubnets = useSelector((state: RootState) =>
    subnetSelectors.getByPod(state, pod)
  );
  const pxeSubnets = useSelector((state: RootState) =>
    subnetSelectors.getPxeEnabledByPod(state, pod)
  );
  const composingPods = useSelector(podSelectors.composing);
  const fabrics = useSelector(fabricSelectors.all);
  const spaces = useSelector(spaceSelectors.all);
  const vlans = useSelector(vlanSelectors.all);

  const { handleChange, setFieldValue, values } =
    useFormikContext<ComposeFormValues>();
  const { interfaces } = values;
  const hasSubnets = allPodSubnets.length >= 1;
  const hasPxeSubnets = pxeSubnets.length >= 1;
  const canDefineInterfaces =
    hasSubnets && hasPxeSubnets && !composingPods.length;
  const firstPxeSubnet = hasPxeSubnets ? pxeSubnets[0] : null;

  const addInterface = () => {
    const ids = interfaces.map((iface) => iface.id);
    let id = 0;
    while (ids.includes(id)) {
      id++;
    }
    setFieldValue("interfaces", [
      ...interfaces,
      generateNewInterface(id, firstPxeSubnet?.id),
    ]).catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "interfaces",
        "setFieldValue",
        reason as string
      );
    });
  };

  const removeInterface = (id: number) => {
    setFieldValue(
      "interfaces",
      interfaces.filter((iface) => iface.id !== id)
    ).catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "interfaces",
        "setFieldValue",
        reason as string
      );
    });
  };

  return (
    <>
      <div className="u-flex--between">
        <h4>Interfaces</h4>
        <Tooltip
          data-testid="define-interfaces"
          message={getTooltipMessage(hasSubnets, hasPxeSubnets)}
          position="top-left"
        >
          <Button
            disabled={!canDefineInterfaces}
            hasIcon
            onClick={addInterface}
            type="button"
          >
            <i className="p-icon--plus"></i>
            <span>
              {interfaces.length === 0 ? "Define (optional)" : "Add interface"}
            </span>
          </Button>
        </Tooltip>
      </div>
      {interfaces.length >= 1 ? (
        interfaces.map((iface, i) => {
          const subnet = allPodSubnets.find(
            (subnet) => subnet.id === parseInt(iface.subnet)
          );
          const vlan = vlans.find((vlan) => vlan.id === subnet?.vlan);
          const fabric = fabrics.find((fabric) => fabric.id === vlan?.fabric);

          return (
            <Card data-testid="interface" key={iface.id}>
              <FormikField
                label="Name"
                name={`interfaces[${i}].name`}
                type="text"
              />
              <FormikField
                label="IP address"
                name={`interfaces[${i}].ipAddress`}
                placeholder="Leave empty to auto-assign"
                type="text"
              />
              <FormikField
                component={Select}
                label="Space"
                name={`interfaces[${i}].space`}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                  handleChange(e);
                  setFieldValue(`interfaces[${i}].subnet`, "").catch(
                    (reason: unknown) => {
                      throw new FormikFieldChangeError(
                        `interfaces[${i}].subnet`,
                        "setFieldValue",
                        reason as string
                      );
                    }
                  );
                }}
                options={[
                  {
                    label: "Any",
                    value: "",
                  },
                  ...spaces.map((space) => ({
                    key: space.id,
                    label: space.name,
                    value: space.id,
                  })),
                ]}
              />
              <SubnetSelect
                hostId={hostId}
                iface={iface}
                index={i}
                selectSubnet={(subnetID?: number) => {
                  setFieldValue(`interfaces[${i}].subnet`, subnetID).catch(
                    (reason: unknown) => {
                      throw new FormikFieldChangeError(
                        `interfaces[${i}].subnet`,
                        "setFieldValue",
                        reason as string
                      );
                    }
                  );
                }}
              />
              <Row>
                <Col size={4}>
                  <Definition description={fabric?.name || ""} label="Fabric" />
                </Col>
                <Col size={4}>
                  <Definition description={vlan?.name || ""} label="VLAN" />
                </Col>
                <Col size={4}>
                  <Definition label="PXE">
                    <i {...getPxeIconProps(pod, vlan)}></i>
                  </Definition>
                </Col>
              </Row>
              <div className="u-align--right">
                <Button
                  data-testid="delete-interface"
                  disabled={!!composingPods.length}
                  onClick={() => {
                    removeInterface(iface.id);
                  }}
                  type="button"
                >
                  Delete
                </Button>
              </div>
            </Card>
          );
        })
      ) : (
        <>
          <Card data-testid="undefined-interface">
            <Row>
              <Col size={6}>
                <Definition label="Name">
                  <em>default</em>
                </Definition>
              </Col>
              <Col size={6}>
                <Definition label="IP address">
                  Created by hypervisor at compose time
                </Definition>
              </Col>
            </Row>
          </Card>
        </>
      )}
    </>
  );
};

export default InterfacesTable;
