import type { ReactElement } from "react";
import { useEffect } from "react";

import { ContentSection } from "@canonical/maas-react-components";
import { AppAside, useOnEscapePressed } from "@canonical/react-components";
import classNames from "classnames";
import { useLocation } from "react-router";

import { useSidePanel } from "@/app/base/side-panel-context";

const useCloseSidePanelOnRouteChange = (): void => {
  const location = useLocation();
  const { closeSidePanel } = useSidePanel();

  useEffect(
    () => {
      closeSidePanel();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [location.pathname, location.search, location.hash]
  );
};

const useResetSidePanelOnUnmount = (): void => {
  const { setSidePanelSize } = useSidePanel();

  // reset side panel size to default on unmounting
  useEffect(
    () => {
      return () => {
        setSidePanelSize("regular");
      };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );
};

const useCloseSidePanelOnEscPressed = (): void => {
  const { closeSidePanel } = useSidePanel();
  useOnEscapePressed(() => {
    closeSidePanel();
  });
};

const SidePanel = (): ReactElement => {
  useCloseSidePanelOnEscPressed();
  useCloseSidePanelOnRouteChange();
  useResetSidePanelOnUnmount();

  const { isOpen, title, component: Component, props, size } = useSidePanel();

  return (
    <AppAside
      aria-label={title ?? undefined}
      className={classNames({
        "is-narrow": size === "narrow",
        "is-large": size === "large",
        "is-wide": size === "wide",
      })}
      collapsed={!isOpen}
      id="aside-panel"
    >
      <ContentSection>
        {title ? (
          <div className="row section-header section-header--side-panel">
            <div className="col-12">
              <h3 className="section-header__title u-flex--no-shrink p-heading--4">
                {title}
              </h3>
            </div>
          </div>
        ) : null}
        {isOpen && Component && <Component {...props} />}
      </ContentSection>
    </AppAside>
  );
};

export default SidePanel;
