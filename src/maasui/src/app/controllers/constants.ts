import type urls from "./urls";

export const ControllerDetailsTabLabels: Record<
  Exclude<keyof typeof urls.controller, "index">,
  string
> = {
  summary: "Summary",
  vlans: "VLANs",
  network: "Network",
  storage: "Storage",
  pciDevices: "PCI devices",
  usbDevices: "USB",
  commissioning: "Commissioning",
  logs: "Logs",
  configuration: "Configuration",
};
