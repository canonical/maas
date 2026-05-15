import type { MouseEventHandler } from "react";

import { ContextualMenu, useId } from "@canonical/react-components";
import classNames from "classnames";
import type { FormikErrors } from "formik";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { ComposeFormValues, InterfaceField } from "../../ComposeForm";
import { getPxeIconProps } from "../InterfacesTable";

import fabricSelectors from "@/app/store/fabric/selectors";
import type { Fabric } from "@/app/store/fabric/types";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod, PodDetails } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import spaceSelectors from "@/app/store/space/selectors";
import type { Space } from "@/app/store/space/types";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";
import { groupAsMap } from "@/app/utils";

type Props = {
  hostId: Pod["id"];
  iface: InterfaceField;
  index: number;
  selectSubnet: (subnetID?: number) => void;
};

export type MenuLink =
  | string
  | {
      children: React.ReactElement;
      className: string;
      onClick: MouseEventHandler;
    };

/**
 * Filter subnets to those that are in a given space.
 * @param {Subnet[]} subnets - The subnets to filter.
 * @param {Space} space - The space by which to filter subnets.
 * @returns {Subnet[]} Subnets filtered by space.
 */
const filterSubnetsBySpace = (subnets: Subnet[], space: Space): Subnet[] => {
  if (!!space) {
    return subnets.filter((subnet) => subnet.space === space.id);
  }
  return subnets;
};

/**
 * Generate links for use in the select dropdown.
 * @param {Subnet[]} subnets - Subnets in state.
 * @param {VLAN[]} vlans - VLANs in state.
 * @param {Fabric[]} fabrics - Fabrics in state.
 * @param {PodDetails} pod - Pod used to determine PXE state.
 * @param {Function} selectSubnet - Function to run on link click.
 * @returns Subnet links for select dropdown.
 */
const generateLinks = (
  subnets: Subnet[],
  vlans: VLAN[],
  fabrics: Fabric[],
  pod: PodDetails,
  selectSubnet: Props["selectSubnet"]
) =>
  subnets.map((subnet) => {
    const vlan = vlans.find((vlan) => vlan.id === subnet?.vlan);
    const fabric = fabrics.find((fabric) => fabric.id === vlan?.fabric);

    return {
      children: (
        <>
          <div>{subnet?.name || ""}</div>
          <div>{fabric?.name || ""}</div>
          <div>{vlan?.name || ""}</div>
          <div>
            <i {...getPxeIconProps(pod, vlan)}></i>
          </div>
        </>
      ),
      className: "kvm-subnet-select__subnet",
      onClick: () => {
        selectSubnet(subnet.id);
      },
    };
  });

export const SubnetSelect = ({
  hostId,
  iface,
  index,
  selectSubnet,
}: Props): React.ReactElement => {
  const id = useId();
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  ) as PodDetails;
  const podSubnets = useSelector(subnetSelectors.all);
  const fabrics = useSelector(fabricSelectors.all);
  const spaces = useSelector(spaceSelectors.all);
  const vlans = useSelector(vlanSelectors.all);
  const { errors } = useFormikContext<ComposeFormValues>();
  const subnetError =
    errors?.interfaces && errors.interfaces.length >= index + 1
      ? (errors.interfaces[index] as FormikErrors<InterfaceField>)?.subnet
      : null;

  const selectedSpace = spaces.find(
    (space) => space.id === parseInt(iface.space)
  );
  const selectedSubnet = podSubnets.find(
    (subnet) => subnet.id === parseInt(iface.subnet)
  );
  let links: MenuLink[] = [];

  if (selectedSpace) {
    // If space is selected, just show subnets in that space without the space name
    const filteredSubnets = filterSubnetsBySpace(podSubnets, selectedSpace);
    links = links.concat(
      generateLinks(filteredSubnets, vlans, fabrics, pod, selectSubnet)
    );
  } else {
    // If space is not selected, show all subnets grouped by space.
    const spaceGroups = Array.from(
      groupAsMap(podSubnets, (subnet: Subnet) => subnet.space)
    )
      .map(([spaceID, subnets]) => {
        const space = spaces.find((space) => space.id === spaceID);
        return {
          name: space ? `Space: ${space.name}` : "No space",
          subnets,
        };
      })
      .sort(
        (a, b) =>
          (a.name === "No space" && 1) || (b.name === "No space" && -1) || 0
      );
    spaceGroups.forEach((space) => {
      links = links.concat([
        space.name,
        ...generateLinks(space.subnets, vlans, fabrics, pod, selectSubnet),
      ]);
    });
  }

  return (
    <div
      className={classNames("p-form__group", {
        "is-error": Boolean(subnetError),
      })}
    >
      <label className="p-form__label" id={id}>
        Subnet
      </label>
      <ContextualMenu
        className="kvm-subnet-select"
        constrainPanelWidth
        dropdownClassName="kvm-subnet-select__dropdown"
        hasToggleIcon
        links={links}
        position="left"
        toggleClassName={classNames("kvm-subnet-select__toggle", {
          "is-error": Boolean(subnetError),
        })}
        toggleLabel={selectedSubnet?.name || "Select subnet..."}
        toggleProps={{ "aria-describedby": id }}
      />
      {subnetError && (
        <p className="p-form-validation__message" data-testid="no-pxe">
          {subnetError}
        </p>
      )}
    </div>
  );
};

export default SubnetSelect;
