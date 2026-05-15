import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import type {
  ScriptResult,
  ScriptResultMeta,
} from "@/app/store/scriptresult/types";
import { argPath } from "@/app/utils";

const withId = argPath<{ id: Controller[ControllerMeta.PK] }>;
const withIdScriptResultId = argPath<{
  id: Controller[ControllerMeta.PK];
  scriptResultId: ScriptResult[ScriptResultMeta.PK];
}>;

const urls = {
  index: "/controllers",
  controller: {
    commissioning: {
      index: withId("/controller/:id/commissioning"),
      scriptResult: withIdScriptResultId(
        "/controller/:id/commissioning/:scriptResultId/details"
      ),
    },
    configuration: withId("/controller/:id/configuration"),
    index: withId("/controller/:id"),
    logs: {
      events: withId("/controller/:id/logs/events"),
      index: withId("/controller/:id/logs"),
      installationOutput: withId("/controller/:id/logs/installation-output"),
    },
    network: withId("/controller/:id/network"),
    pciDevices: withId("/controller/:id/pci-devices"),
    storage: withId("/controller/:id/storage"),
    summary: withId("/controller/:id/summary"),
    usbDevices: withId("/controller/:id/usb-devices"),
    vlans: withId("/controller/:id/vlans"),
  },
} as const;

export default urls;
