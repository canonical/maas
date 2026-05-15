import type { Machine } from "@/app/store/machine/types";
import type { ScriptResult } from "@/app/store/scriptresult/types";
import { argPath } from "@/app/utils";

const withId = argPath<{ id: Machine["system_id"] }>;
const withIdScriptResultId = argPath<{
  id: Machine["system_id"];
  scriptResultId: ScriptResult["id"];
}>;

const urls = {
  index: "/machines",
  machine: {
    commissioning: {
      index: withId("/machine/:id/commissioning"),
      scriptResult: withIdScriptResultId(
        "/machine/:id/commissioning/:scriptResultId/details"
      ),
    },
    deployment: {
      index: withId("/machine/:id/deployment"),
      scriptResult: withIdScriptResultId(
        "/machine/:id/deployment/:scriptResultId/details"
      ),
    },
    configuration: withId("/machine/:id/configuration"),
    events: withId("/machine/:id/events"),
    index: withId("/machine/:id"),
    instances: withId("/machine/:id/instances"),
    logs: {
      events: withId("/machine/:id/logs/events"),
      index: withId("/machine/:id/logs"),
      installationOutput: withId("/machine/:id/logs/installation-output"),
    },
    network: withId("/machine/:id/network"),
    pciDevices: withId("/machine/:id/pci-devices"),
    scriptsResults: {
      index: withId("/machine/:id/scripts"),
      commissioning: {
        index: withId("/machine/:id/scripts/commissioning"),
        scriptResult: withIdScriptResultId(
          "/machine/:id/scripts/commissioning/:scriptResultId/details"
        ),
      },
      deployment: {
        index: withId("/machine/:id/scripts/deployment"),
        scriptResult: withIdScriptResultId(
          "/machine/:id/scripts/deployment/:scriptResultId/details"
        ),
      },
      testing: {
        index: withId("/machine/:id/scripts/tests"),
        scriptResult: withIdScriptResultId(
          "/machine/:id/scripts/tests/:scriptResultId/details"
        ),
      },
    },
    storage: withId("/machine/:id/storage"),
    summary: withId("/machine/:id/summary"),
    testing: {
      index: withId("/machine/:id/testing"),
      scriptResult: withIdScriptResultId(
        "/machine/:id/testing/:scriptResultId/details"
      ),
    },
    usbDevices: withId("/machine/:id/usb-devices"),
  },
} as const;

export default urls;
