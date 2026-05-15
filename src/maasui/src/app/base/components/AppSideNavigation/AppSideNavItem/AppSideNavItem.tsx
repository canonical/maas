import type { MouseEvent, ReactNode } from "react";

import { Navigation } from "@canonical/maas-react-components";
import classNames from "classnames";
import { Link } from "react-router";

import type { SideNavigationProps } from "../AppSideNavigation";
import type { NavItem } from "../types";
import { isSelected } from "../utils";

import { useId } from "@/app/base/hooks/base";
import { MOBILE_VIEW_MAX_WIDTH } from "@/app/constants";

type Props = {
  navLink: NavItem;
  icon?: ReactNode | string;
  path: string;
  setIsCollapsed: SideNavigationProps["setIsCollapsed"];
};

export const AppSideNavItem = ({
  navLink,
  icon,
  path,
  setIsCollapsed,
}: Props): React.ReactElement => {
  const id = useId();
  return (
    <Navigation.Item
      aria-labelledby={`${navLink.label}-${id}`}
      className={classNames({ "is-selected": isSelected(path, navLink) })}
    >
      <Navigation.Link
        aria-current={isSelected(path, navLink) ? "page" : undefined}
        as={Link}
        id={`${navLink.label}-${id}`}
        onClick={(e: MouseEvent<HTMLAnchorElement>) => {
          // removing the focus from the link element after click
          // this allows the side navigation to collapse on mouseleave
          e.currentTarget.blur();

          if (window.innerWidth < MOBILE_VIEW_MAX_WIDTH) {
            setIsCollapsed(true);
          }
        }}
        to={navLink.url}
      >
        {icon ? (
          typeof icon === "string" ? (
            <Navigation.Icon name={icon} />
          ) : (
            <>{icon}</>
          )
        ) : null}
        <Navigation.Label>{navLink.label}</Navigation.Label>
      </Navigation.Link>
    </Navigation.Item>
  );
};

export default AppSideNavItem;
