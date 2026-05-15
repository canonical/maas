import { IPRangeType } from "./types";
import {
  getCommentDisplay,
  getOwnerDisplay,
  getTypeDisplay,
  isDynamic,
} from "./utils";

import * as factory from "@/testing/factories";

describe("isDynamic", () => {
  it("returns whether an IP range is dynamic", () => {
    const dynamicIP = factory.ipRange({ type: IPRangeType.Dynamic });
    const reservedIP = factory.ipRange({ type: IPRangeType.Reserved });

    expect(isDynamic(dynamicIP)).toBe(true);
    expect(isDynamic(reservedIP)).toBe(false);
  });
});

describe("getCommentDisplay", () => {
  it("correctly formats an IP range's comment", () => {
    const dynamicIP = factory.ipRange({
      comment: "something",
      type: IPRangeType.Dynamic,
    });
    const reservedIP = factory.ipRange({
      comment: "something",
      type: IPRangeType.Reserved,
    });

    expect(getCommentDisplay(dynamicIP)).toBe("Dynamic");
    expect(getCommentDisplay(reservedIP)).toBe("something");
  });
});

describe("getOwnerDisplay", () => {
  it("correctly formats an IP range's owner", () => {
    const dynamicIP = factory.ipRange({
      type: IPRangeType.Dynamic,
      user: "user",
    });
    const reservedIP = factory.ipRange({
      type: IPRangeType.Reserved,
      user: "user",
    });

    expect(getOwnerDisplay(dynamicIP)).toBe("MAAS");
    expect(getOwnerDisplay(reservedIP)).toBe("user");
  });
});

describe("getTypeDisplay", () => {
  it("correctly formats an IP range's type", () => {
    const dynamicIP = factory.ipRange({
      type: IPRangeType.Dynamic,
    });
    const reservedIP = factory.ipRange({
      type: IPRangeType.Reserved,
    });

    expect(getTypeDisplay(dynamicIP)).toBe("Dynamic");
    expect(getTypeDisplay(reservedIP)).toBe("Reserved");
  });
});
