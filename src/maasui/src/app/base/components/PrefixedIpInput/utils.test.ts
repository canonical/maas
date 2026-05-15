import { formatIpAddress } from "./utils";

it("can format an IPv4 address", () => {
  const ip = "10";
  const cidr = "192.168.0.0/24";

  expect(formatIpAddress(ip, cidr)).toBe("192.168.0.10");
});

it("can format an IPv6 address", () => {
  const ip = ":10";
  const cidr = "2001:db8::/32";

  expect(formatIpAddress(ip, cidr)).toBe("2001:db8::10");
});
