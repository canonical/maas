import type { Meta } from "@storybook/react";

import GroupRow from "./GroupRow";

const meta: Meta<typeof GroupRow> = {
  title: "Components/GroupRow",
  component: GroupRow,
  tags: ["autodocs"],
};

export default meta;

export const Example = {
  args: {
    itemName: "network",
    groupName: "fabric",
    count: 2,
  },
};
