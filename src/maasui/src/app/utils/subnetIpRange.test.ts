import {
  getImmutableAndEditableOctets,
  getIpRangeFromCidr,
  isIpInSubnet,
} from "./subnetIpRange";

describe("getIpRangeFromCidr", () => {
  it("returns the start and end IP of a subnet", () => {
    expect(getIpRangeFromCidr("10.0.0.0/26")).toEqual([
      "10.0.0.1",
      "10.0.0.62",
    ]);

    expect(getIpRangeFromCidr("10.0.0.0/25")).toEqual([
      "10.0.0.1",
      "10.0.0.126",
    ]);

    expect(getIpRangeFromCidr("10.0.0.0/24")).toEqual([
      "10.0.0.1",
      "10.0.0.254",
    ]);

    expect(getIpRangeFromCidr("10.0.0.0/23")).toEqual([
      "10.0.0.1",
      "10.0.1.254",
    ]);

    expect(getIpRangeFromCidr("10.0.0.0/22")).toEqual([
      "10.0.0.1",
      "10.0.3.254",
    ]);
  });
});

describe("isIpInSubnet", () => {
  it("returns true if an IP is in a subnet", () => {
    expect(isIpInSubnet("10.0.0.1", "10.0.0.0/24")).toBe(true);
    expect(isIpInSubnet("10.0.0.254", "10.0.0.0/24")).toBe(true);
    expect(isIpInSubnet("192.168.0.1", "192.168.0.0/24")).toBe(true);
    expect(isIpInSubnet("192.168.0.254", "192.168.0.0/24")).toBe(true);
    expect(isIpInSubnet("192.168.1.1", "192.168.0.0/23")).toBe(true);
  });

  it("returns false if an IP is not in a subnet", () => {
    expect(isIpInSubnet("10.0.1.0", "10.0.0.0/24")).toBe(false);
    expect(isIpInSubnet("10.1.0.0", "10.0.0.0/24")).toBe(false);
    expect(isIpInSubnet("11.0.0.0", "10.0.0.0/24")).toBe(false);
    expect(isIpInSubnet("192.168.1.255", "192.168.0.0/23")).toBe(false);
    expect(isIpInSubnet("10.0.0.1", "192.168.0.0/24")).toBe(false);
    expect(isIpInSubnet("192.168.2.1", "192.168.0.0/24")).toBe(false);
    expect(isIpInSubnet("172.16.0.1", "192.168.0.0/24")).toBe(false);
  });

  it("returns false for the network and broadcast addresses", () => {
    expect(isIpInSubnet("10.0.0.0", "10.0.0.0/24")).toBe(false);
    expect(isIpInSubnet("10.0.0.255", "10.0.0.0/24")).toBe(false);
  });
});

describe("getImmutableAndEditableOctets", () => {
  it("returns the immutable and editable octets for a given subnet range", () => {
    expect(getImmutableAndEditableOctets("10.0.0.1", "10.0.0.254")).toEqual([
      "10.0.0",
      "[1-254]",
    ]);
    expect(getImmutableAndEditableOctets("10.0.0.1", "10.0.255.254")).toEqual([
      "10.0",
      "[0-255].[1-254]",
    ]);
    expect(getImmutableAndEditableOctets("10.0.0.1", "10.255.255.254")).toEqual(
      ["10", "[0-255].[0-255].[1-254]"]
    );
    expect(getImmutableAndEditableOctets("10.0.0.1", "20.255.255.254")).toEqual(
      ["", "[10-20].[0-255].[0-255].[1-254]"]
    );
  });
});
