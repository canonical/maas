import { IPAddressType } from "./types";
import {
  getHasIPAddresses,
  getIPTypeDisplay,
  getIPUsageDisplay,
  getSubnetDisplay,
  isSubnetDetails,
} from "./utils";

import { NodeType } from "@/app/store/types/node";
import * as factory from "@/testing/factories";

describe("subnet utils", () => {
  describe("getSubnetDisplay", function () {
    it("returns 'Unconfigured' for null", function () {
      expect(getSubnetDisplay(null)).toBe("Unconfigured");
    });

    it("returns just cidr if name same as cidr", function () {
      const subnet = factory.subnet({ cidr: "same-name", name: "same-name" });
      expect(getSubnetDisplay(subnet)).toBe("same-name");
    });

    it("returns cidr + name", function () {
      const subnet = factory.subnet({ cidr: "cidr-name", name: "subnet-name" });
      expect(getSubnetDisplay(subnet)).toBe("cidr-name (subnet-name)");
    });

    it("can return the short name instead of cidr + name", function () {
      const subnet = factory.subnet({ cidr: "cidr-name", name: "subnet-name" });
      expect(getSubnetDisplay(subnet, true)).toBe("cidr-name");
    });
  });

  describe("isSubnetDetails", () => {
    it("handles the null case", () => {
      expect(isSubnetDetails()).toBe(false);
      expect(isSubnetDetails(null)).toBe(false);
    });

    it("correctly returns whether a subnet is the detailed type", () => {
      const subnet = factory.subnet();
      const subnetDetails = factory.subnetDetails();
      expect(isSubnetDetails(subnet)).toBe(false);
      expect(isSubnetDetails(subnetDetails)).toBe(true);
    });
  });
});

describe("getHasIPAddresses", function () {
  it("handles no arguments provided", function () {
    expect(getHasIPAddresses()).toBe(false);
  });

  it("handles non-details subnets", function () {
    const subnet = factory.subnet();
    expect(getHasIPAddresses(subnet)).toBe(false);
  });

  it("returns true if argument has IP addresses", function () {
    const subnet = factory.subnetDetails({
      ip_addresses: [factory.subnetIP()],
    });
    expect(getHasIPAddresses(subnet)).toBe(true);
  });

  it("returns false if argument has no IP addresses", function () {
    const subnet = factory.subnetDetails({ ip_addresses: [] });
    expect(getHasIPAddresses(subnet)).toBe(false);
  });
});

describe("getIPTypeDisplay", () => {
  it("correctly returns the display text for an IP address type", () => {
    expect(getIPTypeDisplay(IPAddressType.AUTO)).toBe("Automatic");
    expect(getIPTypeDisplay(IPAddressType.DHCP)).toBe("DHCP");
    expect(getIPTypeDisplay(IPAddressType.DISCOVERED)).toBe("Discovered");
    expect(getIPTypeDisplay(IPAddressType.STICKY)).toBe("Sticky");
    expect(getIPTypeDisplay(IPAddressType.USER_RESERVED)).toBe("User reserved");
  });
});

describe("getIPUsageDisplay", () => {
  it("handles an IP used for a container", () => {
    const ip = factory.subnetIP({
      node_summary: factory.subnetIPNodeSummary({
        is_container: true,
        node_type: NodeType.DEVICE,
      }),
    });
    expect(getIPUsageDisplay(ip)).toBe("Container");
  });

  it("handles an IP used for a node", () => {
    const ip = factory.subnetIP({
      node_summary: factory.subnetIPNodeSummary({
        is_container: false,
        node_type: NodeType.MACHINE,
      }),
    });
    expect(getIPUsageDisplay(ip)).toBe("Machine");
  });

  it("handles an IP used in BMCs", () => {
    const ip = factory.subnetIP({ bmcs: [factory.subnetBMC()] });
    expect(getIPUsageDisplay(ip)).toBe("BMC");
  });

  it("handles an IP used in DNS", () => {
    const ip = factory.subnetIP({ dns_records: [factory.subnetDNSRecord()] });
    expect(getIPUsageDisplay(ip)).toBe("DNS");
  });

  it("handles an IP with unknown usage", () => {
    const ip = factory.subnetIP({
      bmcs: undefined,
      dns_records: undefined,
      node_summary: undefined,
    });
    expect(getIPUsageDisplay(ip)).toBe("Unknown");
  });
});
