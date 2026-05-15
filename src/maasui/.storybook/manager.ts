import { addons } from "@storybook/manager-api";

import maasTheme from "./maas-theme";

addons.setConfig({
  theme: maasTheme,
});
