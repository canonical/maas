import type { ReactElement } from "react";
import { useMemo } from "react";

import { Navigation, NavigationBar } from "@canonical/maas-react-components";
import {
  Button,
  ButtonAppearance,
  Icon,
  Tooltip,
} from "@canonical/react-components";
import { useSelector } from "react-redux";
import { useLocation } from "react-router";
import { useStorageState } from "react-storage-hooks";

import { useLogout } from "../../hooks/logout";
import useDarkMode from "../../hooks/useDarkMode/useDarkMode";

import AppSideNavItems from "./AppSideNavItems";
import NavigationBanner from "./NavigationBanner";
import { navGroups } from "./constants";

import { useGetCurrentUser } from "@/app/api/query/auth";
import type { UserResponse } from "@/app/apiclient";
import {
  useCompletedIntro,
  useCompletedUserIntro,
  useFetchActions,
  useGoogleAnalytics,
} from "@/app/base/hooks";
import { useGlobalKeyShortcut } from "@/app/base/hooks/base";
import { useThemeContext } from "@/app/base/theme-context";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors from "@/app/store/controller/selectors";
import { podActions } from "@/app/store/pod";
import podSelectors from "@/app/store/pod/selectors";
import type { RootState } from "@/app/store/root/types";

export type SideNavigationProps = {
  authUser: UserResponse;
  filteredGroups: typeof navGroups;
  isAuthenticated: boolean;
  isCollapsed: boolean;
  isDarkMode: boolean;
  logout: () => void;
  path: string;
  setIsCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  showLinks: boolean;
  theme: string;
  toggleDarkMode: (isDark: boolean) => void;
  vaultIncomplete: boolean;
};

export const AppSideNavigation = ({
  authUser,
  filteredGroups,
  isAuthenticated,
  isCollapsed,
  isDarkMode,
  logout,
  path,
  setIsCollapsed,
  showLinks,
  theme,
  toggleDarkMode,
  vaultIncomplete,
}: SideNavigationProps): ReactElement => (
  <>
    <NavigationBar className={`is-maas-${theme}`}>
      <Navigation.Header>
        <NavigationBanner />
        <Navigation.Controls>
          <NavigationBar.MenuButton
            onClick={() => {
              setIsCollapsed(!isCollapsed);
            }}
          >
            Menu
          </NavigationBar.MenuButton>
        </Navigation.Controls>
      </Navigation.Header>
    </NavigationBar>
    <Navigation className={`is-maas-${theme}`} isCollapsed={isCollapsed}>
      <Navigation.Drawer>
        <Navigation.Header>
          <NavigationBanner>
            <Navigation.Controls>
              <NavigationBar.MenuButton
                onClick={() => {
                  setIsCollapsed(!isCollapsed);
                }}
              >
                Close menu
              </NavigationBar.MenuButton>
              <Navigation.CollapseToggle
                isCollapsed={isCollapsed}
                setIsCollapsed={setIsCollapsed}
              />
            </Navigation.Controls>
          </NavigationBanner>
        </Navigation.Header>
        <Navigation.Content>
          <AppSideNavItems
            authUser={authUser}
            groups={filteredGroups}
            isAdmin={authUser?.is_superuser ?? false}
            isAuthenticated={isAuthenticated}
            logout={logout}
            path={path}
            setIsCollapsed={setIsCollapsed}
            showLinks={showLinks}
            vaultIncomplete={vaultIncomplete}
          />
        </Navigation.Content>
        <div className="u-flex--grow"></div>
        <Tooltip
          className="dark-mode-toggle"
          message={`${isDarkMode ? "Disable" : "Enable"} dark mode`}
          position="right"
        >
          <Button
            appearance={ButtonAppearance.BASE}
            hasIcon
            onClick={() => {
              toggleDarkMode(isDarkMode);
            }}
          >
            <Icon name={isDarkMode ? "highlight-on" : "highlight-off"} />
          </Button>
        </Tooltip>
      </Navigation.Drawer>
    </Navigation>
  </>
);

const AppSideNavigationContainer = (): React.ReactElement => {
  const location = useLocation();
  const path = location.pathname;
  const user = useGetCurrentUser();
  const completedIntro = useCompletedIntro();
  const completedUserIntro = useCompletedUserIntro();
  const isAuthenticated = !!user.data;
  const showLinks = isAuthenticated && completedIntro && completedUserIntro;
  useGoogleAnalytics();

  const logout = useLogout();

  const [isDarkMode, toggleDarkMode] = useDarkMode();

  useFetchActions([controllerActions.fetch]);

  useFetchActions([podActions.fetch]);

  const virshKvms = useSelector(podSelectors.virsh);
  const kvmsLoaded = useSelector(podSelectors.loaded);
  const hideVirsh = kvmsLoaded && virshKvms.length < 1;

  const { unconfiguredControllers, configuredControllers } = useSelector(
    (state: RootState) =>
      controllerSelectors.getVaultConfiguredControllers(state)
  );

  const vaultIncomplete =
    unconfiguredControllers.length >= 1 && configuredControllers.length >= 1;
  const [isCollapsed, setIsCollapsed] = useStorageState<boolean>(
    localStorage,
    "appSideNavIsCollapsed",
    true
  );
  useGlobalKeyShortcut("[", () => {
    setIsCollapsed(!isCollapsed);
  });

  const { theme } = useThemeContext();

  const filteredGroups = useMemo(() => {
    if (hideVirsh) {
      const kvmGroupIndex = navGroups.findIndex(
        (group) => group.groupTitle === "KVM"
      );

      const virshItemIndex = navGroups[kvmGroupIndex].navLinks.findIndex(
        (navLink) => navLink.label === "Virsh"
      );

      if (virshItemIndex > -1) {
        navGroups[kvmGroupIndex].navLinks.splice(virshItemIndex, 1);
      }
    }

    return navGroups;
  }, [hideVirsh]);

  return (
    <AppSideNavigation
      authUser={user.data!}
      filteredGroups={filteredGroups}
      isAuthenticated={isAuthenticated}
      isCollapsed={isCollapsed}
      isDarkMode={isDarkMode}
      logout={logout}
      path={path}
      setIsCollapsed={setIsCollapsed}
      showLinks={showLinks}
      theme={theme}
      toggleDarkMode={toggleDarkMode}
      vaultIncomplete={vaultIncomplete}
    />
  );
};

export default AppSideNavigationContainer;
