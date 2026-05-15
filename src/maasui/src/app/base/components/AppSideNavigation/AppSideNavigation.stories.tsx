import type { ReactElement } from "react";

import { Application } from "@canonical/react-components";
import type { Meta } from "@storybook/react";

import { AppSideNavigation } from "./AppSideNavigation";
import { navGroups } from "./constants";

import { user as userFactory } from "@/testing/factories";

const meta: Meta<typeof AppSideNavigation> = {
  title: "Layout/AppSideNavigation",
  component: AppSideNavigation,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
  decorators: [
    (Story): ReactElement => (
      <Application>
        <Story />
      </Application>
    ),
  ],
};
export default meta;

const args = {
  authUser: userFactory(),
  filteredGroups: navGroups,
  isAdmin: true,
  isAuthenticated: true,
  isCollapsed: true,
  setIsCollapsed: (): void => {},
  logout: (): void => {},
  path: "/",
  showLinks: true,
  theme: "default",
  vaultIncomplete: true,
};

export const LoggedIn = {
  args,
};

export const LoggedOut = {
  args: {
    ...args,
    authUser: null,
    isAuthenticated: false,
  },
};
