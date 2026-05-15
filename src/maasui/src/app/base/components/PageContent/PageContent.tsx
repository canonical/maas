import type { HTMLProps, ReactElement, ReactNode } from "react";

import { AppMain } from "@canonical/react-components";
import classNames from "classnames";
import { useSelector } from "react-redux";
import { matchPath, useLocation } from "react-router";

import ErrorBoundary from "../ErrorBoundary/ErrorBoundary";
import MainContentSection from "../MainContentSection";
import SecondaryNavigation from "../SecondaryNavigation";

import SidePanel from "@/app/base/components/SidePanel";
import { useThemeContext } from "@/app/base/theme-context";
import { preferencesNavItems } from "@/app/preferences/constants";
import { settingsNavItems } from "@/app/settings/constants";
import status from "@/app/store/status/selectors";

export type PageContentProps = HTMLProps<HTMLDivElement> & {
  children?: ReactNode;
  header?: ReactNode;
  sidebar?: ReactNode;
  isNotificationListHidden?: boolean;
};

const PageContent = ({
  children,
  header,
  sidebar,
  ...props
}: PageContentProps): ReactElement => {
  const { pathname } = useLocation();
  const isSettingsPage = !!matchPath("settings/*", pathname);
  const isPreferencesPage = !!matchPath("account/prefs/*", pathname);
  const authenticated = useSelector(status.authenticated);
  const connected = useSelector(status.connected);
  const hasSecondaryNav = isSettingsPage || isPreferencesPage;
  const isSecondaryNavVisible = hasSecondaryNav && authenticated && connected;
  const { theme } = useThemeContext();

  return (
    <>
      <AppMain>
        {isSecondaryNavVisible ? (
          <div
            className={classNames("l-main__nav", `is-maas-${theme}--accent`)}
          >
            <SecondaryNavigation
              isOpen={isSecondaryNavVisible}
              items={isSettingsPage ? settingsNavItems : preferencesNavItems}
              title={isSettingsPage ? "Settings" : "My preferences"}
            />
          </div>
        ) : null}
        <div className="l-main__content" id="main-content">
          <MainContentSection header={header} {...props}>
            <ErrorBoundary>{children}</ErrorBoundary>
          </MainContentSection>
        </div>
      </AppMain>
      <SidePanel />
    </>
  );
};

export default PageContent;
