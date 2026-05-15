import type { Meta } from "@storybook/react";

import TooltipButton from ".";

const meta: Meta<typeof TooltipButton> = {
  title: "Components/TooltipButton",
  component: TooltipButton,
  tags: ["autodocs"],
};
export default meta;

export const Example = {
  args: {
    children: <span>Tooltip button</span>,
    message: "tooltipMessage",
  },
};
