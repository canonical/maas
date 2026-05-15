import type { ReactElement } from "react";

import type { MenuLink } from "@canonical/react-components";
import { ContextualMenu, Icon } from "@canonical/react-components";
import { useSelector } from "react-redux";

import { useMachineActionMenus } from "../hooks";
import type { MachineActionsProps } from "../types";

import machineSelectors from "@/app/store/machine/selectors";
import type { RootState } from "@/app/store/root/types";
import { canOpenActionForm } from "@/app/store/utils";

import "./_index.scss";

type MachineActionMenuBarProps = MachineActionsProps;

const MachineActionMenuBar = ({
  disabledActions,
  excludeActions,
  isViewingDetails = false,
  systemId,
}: MachineActionMenuBarProps): ReactElement => {
  const actionMenus = useMachineActionMenus(isViewingDetails, systemId);

  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  return (
    <span className="p-node-action-menu-group">
      {actionMenus.map((menu) => (
        <span className="p-action-button--wrapper" key={menu.title}>
          {menu.render ? (
            menu.render()
          ) : (
            <ContextualMenu
              dropdownProps={{ "aria-label": `${menu.title} submenu` }}
              hasToggleIcon
              links={menu.items.reduce<MenuLink[]>((links, item) => {
                if (
                  excludeActions &&
                  excludeActions.some((action) => action === item.action)
                ) {
                  return links;
                }

                if (
                  disabledActions &&
                  disabledActions.some((action) => action === item.action)
                ) {
                  links.push({
                    children: (
                      <div className="u-flex--between">
                        <span>{item.label}...</span>
                      </div>
                    ),
                    disabled: true,
                    onClick: item.onClick,
                  });

                  return links;
                }

                if (!machine) {
                  links.push({
                    children: (
                      <div className="u-flex--between">
                        <span>{item.label}...</span>
                      </div>
                    ),
                    onClick: item.onClick,
                  });
                } else if (canOpenActionForm(machine, item.action)) {
                  links.push({
                    children: (
                      <div className="u-flex--between">
                        <span>{item.label}...</span>
                      </div>
                    ),
                    onClick: item.onClick,
                  });
                }

                return links;
              }, [])}
              position="left"
              toggleLabel={
                !menu.icon ? (
                  menu.title
                ) : (
                  <>
                    <Icon name={menu.icon} />
                    {menu.title}
                  </>
                )
              }
            />
          )}
        </span>
      ))}
    </span>
  );
};

export default MachineActionMenuBar;
