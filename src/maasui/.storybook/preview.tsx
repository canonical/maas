import { Root } from "../src";

import type { Preview } from "@storybook/react";

import "../src/scss/index.scss";

const preview: Preview = {
  parameters: {
    // Add Storybook actions for matching props by default (e.g. onClick, setContent).
    // Can be overriden in stories.
    // https://storybook.js.org/docs/react/essentials/actions#automatically-matching-args
    actions: { argTypesRegex: "^on[A-Z].*|^set[A-Z].*" },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/,
      },
    },
  },
  decorators: [
    (Story) => (
      <Root>
        <Story />
      </Root>
    ),
  ],
};

export default preview;
