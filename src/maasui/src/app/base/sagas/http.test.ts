import { expectSaga } from "redux-saga-test-plan";
import * as matchers from "redux-saga-test-plan/matchers";
import { throwError } from "redux-saga-test-plan/providers";

import {
  api,
  checkAuthenticatedSaga,
  loginSaga,
  logoutSaga,
  externalLoginSaga,
  uploadScriptSaga,
  fetchLicenseKeysSaga,
  updateLicenseKeySaga,
  deleteLicenseKeySaga,
  addMachineChassisSaga,
  ROOT_API,
  SERVICE_API,
} from "./http";

import { ScriptType } from "@/app/store/script/types";
import { ScriptResultNames } from "@/app/store/scriptresult/types";
import { getCookie } from "@/app/utils";
import * as factory from "@/testing/factories";

vi.mock("@/bakery");

describe("Auth API", () => {
  beforeEach(() => {
    fetchMock.resetMocks();
  });

  describe("check authenticated", () => {
    it("returns a SUCCESS action", () => {
      const payload = { authenticated: true };
      return expectSaga(checkAuthenticatedSaga)
        .provide([[matchers.call.fn(api.auth.checkAuthenticated), payload]])
        .put({ type: "status/checkAuthenticatedStart" })
        .put({
          type: "status/checkAuthenticatedSuccess",
          payload,
        })
        .run();
    });

    it("handles errors", () => {
      const error = new Error("kerblam!");
      return expectSaga(checkAuthenticatedSaga)
        .provide([
          [matchers.call.fn(api.auth.checkAuthenticated), throwError(error)],
        ])
        .put({ type: "status/checkAuthenticatedStart" })
        .put({
          error: true,
          type: "status/checkAuthenticatedError",
          payload: error.message,
        })
        .run();
    });
  });

  describe("login", () => {
    it("returns a SUCCESS action", () => {
      const payload = {
        username: "koala",
        password: "gumtree",
      };
      const action = {
        type: "status/login",
        payload,
      };
      return expectSaga(loginSaga, action)
        .provide([[matchers.call.fn(api.auth.login), payload]])
        .put({ type: "status/loginStart" })
        .put({ type: "status/loginSuccess" })
        .put({ type: "status/websocketConnect" })
        .run();
    });

    it("handles errors", () => {
      const payload = {
        username: "koala",
        password: "gumtree",
      };
      const action = {
        type: "status/login",
        payload,
      };
      const error = {
        message: "Username not provided",
        name: "error",
      };
      return expectSaga(loginSaga, action)
        .provide([[matchers.call.fn(api.auth.login), throwError(error)]])
        .put({ type: "status/loginStart" })
        .put({ type: "status/loginError", error: true, payload: error })
        .run();
    });

    it("encodes special characters", () => {
      void api.auth.login({
        username: "ko&ala",
        password: "gum%tree",
      });
      expect(fetch).toHaveBeenCalled();
      // @ts-expect-error since the previous expect passed, the indexing is safe to be considered defined
      expect(fetchMock.mock.calls[0][1]?.body?.toString()).toBe(
        "username=ko%26ala&password=gum%25tree"
      );
    });
  });

  describe("externalLogin", () => {
    it("returns a SUCCESS action", () => {
      return expectSaga(externalLoginSaga)
        .provide([[matchers.call.fn(api.auth.externalLogin), null]])
        .put({ type: "status/externalLoginStart" })
        .put({ type: "status/externalLoginSuccess" })
        .put({ type: "status/websocketConnect" })
        .run();
    });

    it("handles errors", () => {
      const error = new Error("Unable to log in");
      return expectSaga(externalLoginSaga)
        .provide([
          [matchers.call.fn(api.auth.externalLogin), throwError(error)],
        ])
        .put({ type: "status/externalLoginStart" })
        .put({
          type: "status/externalLoginError",
          error: true,
          payload: error.message,
        })
        .run();
    });
  });

  describe("logout", () => {
    it("returns a SUCCESS action", () => {
      return expectSaga(logoutSaga)
        .provide([
          [matchers.call.fn(getCookie), "csrf-token"],
          [matchers.call.fn(api.auth.logout), "csrf-token"],
        ])
        .put({ type: "status/logoutStart" })
        .put({ type: "status/logoutSuccess" })
        .put({ type: "status/websocketDisconnect" })
        .run();
    });

    it("handles errors", () => {
      const error = new Error("Username not provided");
      return expectSaga(logoutSaga)
        .provide([
          [matchers.call.fn(getCookie), "csrf-token"],
          [matchers.call.fn(api.auth.logout), throwError(error)],
        ])
        .put({ type: "status/logoutStart" })
        .put({
          type: "status/logoutError",
          error: true,
          payload: { error: error.message },
        })
        .run();
    });
  });
});

describe("Scripts API", () => {
  describe("upload scripts", () => {
    it("returns a SUCCESS action", () => {
      const script = {
        name: "script-1",
        type: ScriptType.COMMISSIONING,
        contents: "#!/bin/sh/necho 'hi'",
      };
      const action = {
        type: "script/upload",
        payload: script,
      };
      return expectSaga(uploadScriptSaga, action)
        .provide([
          [matchers.call.fn(getCookie), "csrf-token"],
          [matchers.call.fn(api.scripts.upload), script],
        ])
        .put({ type: "script/uploadStart" })
        .put({ type: "script/uploadSuccess", payload: script })
        .run();
    });

    it("handles errors", () => {
      const script = {
        name: "script-1",
        type: ScriptType.COMMISSIONING,
        contents: "#!/bin/sh/necho 'hi'",
      };
      const action = { type: "script/upload", payload: script };
      const error = {
        message: "Script with that name already exists",
        name: "error",
      };
      return expectSaga(uploadScriptSaga, action)
        .provide([
          [matchers.call.fn(getCookie), "csrf-token"],
          [matchers.call.fn(api.scripts.upload), throwError(error)],
        ])
        .put({ type: "script/uploadStart" })
        .put({
          errors: true,
          payload: error,
          type: "script/uploadError",
        })
        .run();
    });
  });
});

describe("License Key API", () => {
  describe("fetch license keys", () => {
    it("returns a SUCCESS action", () => {
      const payload = [{ osystem: "windows", distro_series: "2012" }];
      return expectSaga(fetchLicenseKeysSaga)
        .provide([
          [matchers.call.fn(getCookie), "csrf-token"],
          [matchers.call.fn(api.licenseKeys.fetch), payload],
        ])
        .put({ type: "licensekeys/fetchStart" })
        .put({ type: "licensekeys/fetchSuccess", payload })
        .run();
    });
  });

  describe("update license keys", () => {
    it("returns a SUCCESS action", () => {
      const payload = {
        id: 1,
        osystem: "windows",
        distro_series: "2012",
        license_key: "foo",
        resource_uri: "/key",
      };
      const action = {
        type: "licensekeys/update",
        payload,
      };
      return expectSaga(updateLicenseKeySaga, action)
        .provide([
          [matchers.call.fn(getCookie), "csrf-token"],
          [matchers.call.fn(api.licenseKeys.update), payload],
        ])
        .put({ type: "licensekeys/updateStart" })
        .put({ type: "licensekeys/updateSuccess", payload })
        .run();
    });
  });

  describe("delete license keys", () => {
    it("returns a SUCCESS action", () => {
      const payload = { osystem: "windows", distro_series: "2012" };
      const action = {
        type: "licensekeys/delete",
        payload,
      };
      return expectSaga(deleteLicenseKeySaga, action)
        .provide([
          [matchers.call.fn(getCookie), "csrf-token"],
          [matchers.call.fn(api.licenseKeys.delete), true],
        ])
        .put({ type: "licensekeys/deleteStart" })
        .put({ type: "licensekeys/deleteSuccess", payload })
        .run();
    });
  });
});

describe("Machines API", () => {
  describe("add machine chassis", () => {
    it("returns a success action", () => {
      const payload = {
        params: {
          chassis_type: "powerkvm",
          hostname: "qemu+ssh://virsh@127.0.0.1/system",
        },
      };
      const action = {
        type: "machine/addChassis",
        payload,
      };
      return expectSaga(addMachineChassisSaga, action)
        .provide([
          [matchers.call.fn(getCookie), "csrf-token"],
          [matchers.call.fn(api.machines.addChassis), payload],
        ])
        .put({ type: "machine/addChassisStart" })
        .put({ type: "machine/addChassisSuccess", payload })
        .run();
    });

    it("handles errors", () => {
      const payload = {
        params: {
          hostname: "qemu+ssh://virsh@127.0.0.1/system",
        },
      };
      const action = { type: "machine/addChassis", payload };
      const error = new Error("Chassis type not provided");
      return expectSaga(addMachineChassisSaga, action)
        .provide([
          [matchers.call.fn(getCookie), "csrf-token"],
          [matchers.call.fn(api.machines.addChassis), throwError(error)],
        ])
        .put({ type: "machine/addChassisStart" })
        .put({
          type: "machine/addChassisError",
          payload: error,
        })
        .run();
    });
  });
});

describe("scriptresults", () => {
  describe("download", () => {
    beforeEach(() => {
      fetchMock.resetMocks();
    });

    it("handles a tar.xz file", async () => {
      const blob = new Blob();
      fetchMock.mockResponseOnce(JSON.stringify(blob));
      const response = await api.scriptresults.download(
        "abc123",
        "current-installation",
        ScriptResultNames.CURTIN_LOG,
        "tar.xz"
      );
      expect(response).toMatchObject(blob);
      expect(fetch).toHaveBeenCalledWith(
        `${ROOT_API}nodes/abc123/results/current-installation/?op=download` +
          "&filetype=tar.xz&filters=%2Ftmp%2Fcurtin-logs.tar",
        expect.anything()
      );
    });

    it("handles a txt file", async () => {
      fetchMock.mockResponse("file contents");
      const response = await api.scriptresults.download(
        "abc123",
        "current-installation",
        "/tmp/curtin-logs.txt",
        "txt"
      );
      expect(response).toBe("file contents");
      expect(fetch).toHaveBeenCalledWith(
        `${ROOT_API}nodes/abc123/results/current-installation/?op=download` +
          "&filetype=txt&filters=%2Ftmp%2Fcurtin-logs.txt",
        expect.anything()
      );
    });

    it("handles errors", async () => {
      const errorMessage = new Error("Uh oh!");
      fetchMock.mockReject(errorMessage);
      const error = await api.scriptresults
        .download(
          "abc123",
          "current-installation",
          ScriptResultNames.CURTIN_LOG,
          "txt"
        )
        .catch((error: unknown) => error);
      expect(error).toBe(errorMessage);
    });
  });

  describe("getCurtinLogsTar", () => {
    beforeEach(() => {
      fetchMock.resetMocks();
    });

    it("can fetch a curtin log", async () => {
      const testFile = "test file";
      fetchMock.mockResponse(testFile);
      const response = await api.scriptresults.getCurtinLogsTar("abc123");
      expect(response).toBe(testFile);
      expect(fetch).toHaveBeenCalledWith(
        `${ROOT_API}nodes/abc123/results/current-installation/?op=download` +
          "&filters=%2Ftmp%2Fcurtin-logs.tar",
        expect.anything()
      );
    });
  });
});

describe("zone list API", () => {
  beforeEach(() => {
    fetchMock.resetMocks();
  });

  it("can fetch zones", async () => {
    const zones = [factory.zone()];
    fetchMock.mockResponse(JSON.stringify(zones));
    const response = await api.zones.fetch("csrf-token");
    expect(response).toMatchObject(zones);
    expect(fetch).toHaveBeenCalledWith(
      `${SERVICE_API}zones`,
      expect.anything()
    );
  });
});
