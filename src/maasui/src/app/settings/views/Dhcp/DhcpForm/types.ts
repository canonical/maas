import type { DHCPSnippet } from "@/app/store/dhcpsnippet/types";

export type DHCPFormValues = {
  description: DHCPSnippet["description"];
  enabled: DHCPSnippet["enabled"];
  entity: string;
  name: DHCPSnippet["name"];
  value: DHCPSnippet["value"];
  type: "" | "controller" | "device" | "machine" | "subnet";
};
