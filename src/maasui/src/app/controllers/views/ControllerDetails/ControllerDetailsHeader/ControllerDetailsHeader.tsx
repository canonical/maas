import { useState } from "react";

import { useSelector } from "react-redux";
import { Link, useLocation } from "react-router";

import ControllerName from "./ControllerName";

import NodeActionMenu from "@/app/base/components/NodeActionMenu";
import SectionHeader from "@/app/base/components/SectionHeader";
import { useSendAnalytics } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import ControllerActionFormWrapper from "@/app/controllers/components/ControllerForms/ControllerActionFormWrapper";
import { ControllerDetailsTabLabels } from "@/app/controllers/constants";
import controllerSelectors from "@/app/store/controller/selectors";
import type {
  Controller,
  ControllerActions,
} from "@/app/store/controller/types";
import { isControllerDetails } from "@/app/store/controller/utils";
import type { RootState } from "@/app/store/root/types";
import { getNodeActionTitle } from "@/app/store/utils";

type Props = {
  systemId: Controller["system_id"];
};

const ControllerDetailsHeader = ({ systemId }: Props): React.ReactElement => {
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  const { pathname } = useLocation();
  const [isEditing, setIsEditing] = useState(false);
  const sendAnalytics = useSendAnalytics();
  const { openSidePanel } = useSidePanel();

  if (!controller) {
    return <SectionHeader loading />;
  }

  return (
    <SectionHeader
      buttons={[
        <NodeActionMenu
          filterActions
          hasSelection={true}
          key="action-dropdown"
          nodeDisplay="controller"
          nodes={[controller]}
          onActionClick={(action) => {
            const title = getNodeActionTitle(action);
            sendAnalytics("Controller details action form", title, "Open");
            openSidePanel({
              component: ControllerActionFormWrapper,
              props: {
                // action is a NodeAction, but is guarenteed to be a NodeAction that comprises ControllerActions.
                action: action as ControllerActions,
                controllers: [controller],
                viewingDetails: false,
              },
              title,
            });
          }}
        />,
      ]}
      subtitleLoading={!isControllerDetails(controller)}
      tabLinks={[
        {
          label: ControllerDetailsTabLabels.summary,
          url: urls.controllers.controller.summary({ id: systemId }),
        },
        {
          label: ControllerDetailsTabLabels.vlans,
          url: urls.controllers.controller.vlans({ id: systemId }),
        },
        {
          label: ControllerDetailsTabLabels.network,
          url: urls.controllers.controller.network({ id: systemId }),
        },
        {
          label: ControllerDetailsTabLabels.storage,
          url: urls.controllers.controller.storage({ id: systemId }),
        },
        {
          label: ControllerDetailsTabLabels.pciDevices,
          url: urls.controllers.controller.pciDevices({ id: systemId }),
        },
        {
          label: ControllerDetailsTabLabels.usbDevices,
          url: urls.controllers.controller.usbDevices({ id: systemId }),
        },
        {
          label: ControllerDetailsTabLabels.commissioning,
          url: urls.controllers.controller.commissioning.index({
            id: systemId,
          }),
        },
        {
          label: ControllerDetailsTabLabels.logs,
          url: urls.controllers.controller.logs.index({ id: systemId }),
        },
        {
          label: ControllerDetailsTabLabels.configuration,
          url: urls.controllers.controller.configuration({ id: systemId }),
        },
      ].map((link) => ({
        active: pathname.startsWith(link.url),
        component: Link,
        label: link.label,
        to: link.url,
      }))}
      title={
        <ControllerName
          id={controller.system_id}
          isEditing={isEditing}
          setIsEditing={setIsEditing}
        />
      }
      titleElement={isEditing ? "div" : "h1"}
    />
  );
};

export default ControllerDetailsHeader;
