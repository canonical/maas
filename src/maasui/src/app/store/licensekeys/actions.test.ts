import { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("licenseKeys actions", () => {
  it("can create a license key", () => {
    const payload = {
      osystem: "windows",
      distro_series: "2012",
      license_key: "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
    };

    expect(actions.create(payload)).toEqual({
      type: "licensekeys/create",
      payload,
    });
  });

  it("can fetch license keys", () => {
    expect(actions.fetch()).toEqual({
      payload: null,
      type: "licensekeys/fetch",
    });
  });

  it("can delete license keys", () => {
    const payload = factory.licenseKeys({
      osystem: "windows",
      distro_series: "2012",
    });
    expect(actions.delete(payload)).toEqual({
      type: "licensekeys/delete",
      payload,
    });
  });

  it("can update license keys", () => {
    const payload = factory.licenseKeys({
      osystem: "windows",
      distro_series: "2012",
    });
    expect(actions.update(payload)).toEqual({
      type: "licensekeys/update",
      payload,
    });
  });

  it("can clean up license keys", () => {
    expect(actions.cleanup()).toEqual({
      type: "licensekeys/cleanup",
    });
  });
});
