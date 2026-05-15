import { useMemo } from "react";

import { Navigation } from "@canonical/maas-react-components";
import { Button, Icon } from "@canonical/react-components";

import AppSideNavItem from "../AppSideNavItem";
import type { SideNavigationProps } from "../AppSideNavigation";
import type { NavGroup } from "../types";
import { isSelected } from "../utils";

import type { UserResponse } from "@/app/apiclient";
import { useId } from "@/app/base/hooks/base";
import urls from "@/app/base/urls";

type Props = {
  authUser: UserResponse | null;
  groups: NavGroup[];
  isAdmin: boolean;
  isAuthenticated: boolean;
  logout: () => void;
  path: string;
  setIsCollapsed: SideNavigationProps["setIsCollapsed"];
  showLinks: boolean;
  vaultIncomplete: boolean;
};

const AppSideNavItemGroup = ({
  group,
  isAdmin,
  vaultIncomplete,
  path,
  setIsCollapsed,
}: Pick<Props, "isAdmin" | "path" | "setIsCollapsed" | "vaultIncomplete"> & {
  group: NavGroup;
}) => {
  const id = useId();
  const hasActiveChild = useMemo(() => {
    for (const navLink of group.navLinks) {
      if (isSelected(path, navLink)) {
        return true;
      }
    }
    return false;
  }, [group, path]);

  return (
    <>
      <Navigation.Item hasActiveChild={hasActiveChild}>
        <Navigation.Text key={`${group.groupTitle}-${id}`}>
          {group.groupIcon ? <Navigation.Icon name={group.groupIcon} /> : null}
          <Navigation.Label id={`${group.groupTitle}-${id}`} variant="group">
            {group.groupTitle}
          </Navigation.Label>
        </Navigation.Text>
        <Navigation.List aria-labelledby={`${group.groupTitle}-${id}`}>
          {group.navLinks.map((navLink) => {
            if (!navLink.adminOnly || isAdmin) {
              return (
                <AppSideNavItem
                  icon={
                    navLink.label === "Controllers" && vaultIncomplete ? (
                      <Icon
                        aria-label="warning"
                        data-testid="warning-icon"
                        name="security-warning-grey"
                      />
                    ) : undefined
                  }
                  key={navLink.label}
                  navLink={navLink}
                  path={path}
                  setIsCollapsed={setIsCollapsed}
                />
              );
            } else return null;
          })}
        </Navigation.List>
      </Navigation.Item>
    </>
  );
};

export const AppSideNavItems = ({
  authUser,
  groups,
  isAdmin,
  isAuthenticated,
  logout,
  path,
  setIsCollapsed,
  showLinks,
  vaultIncomplete,
}: Props): React.ReactElement => {
  return (
    <>
      {showLinks ? (
        <ul className="p-side-navigation__list">
          {groups.map((group, i) => (
            <AppSideNavItemGroup
              group={group}
              isAdmin={isAdmin}
              key={`${i}-${group.groupTitle}`}
              path={path}
              setIsCollapsed={setIsCollapsed}
              vaultIncomplete={vaultIncomplete}
            />
          ))}
        </ul>
      ) : null}
      {isAuthenticated ? (
        <>
          {isAdmin && showLinks ? (
            <ul className="p-side-navigation__list">
              <>
                <AppSideNavItem
                  icon="settings"
                  navLink={{ label: "Settings", url: urls.settings.index }}
                  path={path}
                  setIsCollapsed={setIsCollapsed}
                />
              </>
            </ul>
          ) : null}
          <ul className="p-side-navigation__list">
            <AppSideNavItem
              icon="profile"
              navLink={{
                label: `${authUser?.username}`,
                url: urls.preferences.index,
              }}
              path={path}
              setIsCollapsed={setIsCollapsed}
            />

            <ul className="p-side-navigation__list">
              <li className="p-side-navigation__item">
                <Button
                  appearance="link"
                  className="p-side-navigation__button p-side-navigation__link"
                  onClick={() => {
                    logout();
                  }}
                >
                  <span className="p-side-navigation__label">Log out</span>
                </Button>
              </li>
            </ul>
          </ul>
        </>
      ) : null}
    </>
  );
};

export default AppSideNavItems;
