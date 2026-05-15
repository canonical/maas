import classNames from "classnames";
import type { Location } from "react-router";
import { Link, matchPath, useLocation } from "react-router";

import { useThemeContext } from "@/app/base/theme-context";

export type NavItem = {
  label: string;
  path?: string;
  items?: NavItem[];
};

type ItemProps = { item: NavItem };

const SideNavigationLink = ({ item }: ItemProps) => {
  const location = useLocation();
  const isActive = getIsActive({ item, location });
  if (!item.path) {
    return null;
  }
  return (
    <Link
      aria-current={isActive ? "page" : undefined}
      className={classNames("p-side-navigation__link", {
        "is-active": isActive,
      })}
      to={item.path}
    >
      {item.label}
    </Link>
  );
};

const SubNavItem = ({ item }: ItemProps) => {
  return (
    <li className="p-side-navigation__item" key={item.path}>
      <SideNavigationLink item={item} />
    </li>
  );
};

const SubNavigation = ({ items }: { items: NavItem["items"] }) => {
  if (!items || !items.length) return null;

  return (
    <ul className="p-side-navigation__list">
      {items.map((item) => (
        <SubNavItem item={item} key={item.path} />
      ))}
    </ul>
  );
};

const getIsActive = ({
  item,
  location,
}: ItemProps & { location: Location }) => {
  const path = item.path;

  if (!path) {
    return false;
  }

  if (!item.items) {
    return location.pathname.startsWith(path);
  }

  return matchPath(path, location.pathname);
};

const SideNavigationItem = ({ item }: ItemProps) => {
  const location = useLocation();
  const isActive = getIsActive({ item, location });
  const itemClassName = classNames("p-side-navigation__item--title", {
    "is-active": isActive,
  });

  return (
    <li className={itemClassName} key={item.path || item.label}>
      {item.path ? (
        <SideNavigationLink item={item} />
      ) : (
        <span className="p-side-navigation__text p-side-navigation__item">
          {item.label}
        </span>
      )}
      {item.items ? <SubNavigation items={item.items} /> : null}
    </li>
  );
};

export const SecondaryNavigation = ({
  isOpen,
  items,
  title,
}: {
  isOpen?: boolean;
  items: NavItem[];
  title: string;
}): React.ReactElement => {
  const { theme } = useThemeContext();

  return (
    <div
      className={classNames(`p-side-navigation is-dark`, {
        "is-open": isOpen,
      })}
    >
      <nav
        className={`p-side-navigation__drawer is-maas-${theme}--accent u-padding-top--medium`}
      >
        <h2
          className="p-side-navigation__title p-heading--4 p-panel__logo-name u-no-padding--top"
          data-testid="section-header-title"
        >
          {title}
        </h2>
        <ul className="p-side-navigation__list">
          {items.map((item) => (
            <SideNavigationItem item={item} key={item.label} />
          ))}
        </ul>
      </nav>
    </div>
  );
};

export default SecondaryNavigation;
