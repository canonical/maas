import config from "./selectors";

import { ConfigNames } from "@/app/store/config/types";
import * as factory from "@/testing/factories";

describe("config selectors", () => {
  describe("all", () => {
    it("returns list of all MAAS configs", () => {
      const allConfigs = [factory.config(), factory.config()];
      const state = factory.rootState({
        config: factory.configState({
          items: allConfigs,
        }),
      });
      expect(config.all(state)).toStrictEqual(allConfigs);
    });
  });

  describe("errors", () => {
    it("returns config errors", () => {
      const state = factory.rootState({
        config: factory.configState({
          errors: "It's all broken",
        }),
      });
      expect(config.errors(state)).toStrictEqual("It's all broken");
    });
  });

  describe("loading", () => {
    it("returns config loading state", () => {
      const state = factory.rootState({
        config: factory.configState({
          loading: false,
        }),
      });
      expect(config.loading(state)).toStrictEqual(false);
    });
  });

  describe("loaded", () => {
    it("returns config loaded state", () => {
      const state = factory.rootState({
        config: factory.configState({
          loaded: true,
        }),
      });
      expect(config.loaded(state)).toStrictEqual(true);
    });
  });

  describe("saved", () => {
    it("returns config saved state", () => {
      const state = factory.rootState({
        config: factory.configState({
          saved: true,
        }),
      });
      expect(config.saved(state)).toStrictEqual(true);
    });
  });

  describe("defaultStorageLayout", () => {
    it("returns MAAS config for default storage layout", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.DEFAULT_STORAGE_LAYOUT,
              value: "bcache",
            }),
          ],
        }),
      });
      expect(config.defaultStorageLayout(state)).toBe("bcache");
    });
  });

  describe("storageLayoutOptions", () => {
    it("returns array of storage layout options, formatted as objects", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.DEFAULT_STORAGE_LAYOUT,
              value: "bcache",
              choices: [
                ["bcache", "Bcache layout"],
                ["blank", "No storage (blank) layout"],
              ],
            }),
          ],
        }),
      });
      expect(config.storageLayoutOptions(state)).toStrictEqual([
        {
          value: "bcache",
          label: "Bcache layout",
        },
        {
          value: "blank",
          label: "No storage (blank) layout",
        },
      ]);
    });
  });

  describe("enableDiskErasing", () => {
    it("returns MAAS config for enabling disk erase on release", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.ENABLE_DISK_ERASING_ON_RELEASE,
              value: "foo",
            }),
          ],
        }),
      });
      expect(config.enableDiskErasing(state)).toBe("foo");
    });
  });

  describe("diskEraseWithSecure", () => {
    it("returns MAAS config for enabling disk erase with secure erase", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.DISK_ERASE_WITH_SECURE_ERASE,
              value: "bar",
            }),
          ],
        }),
      });
      expect(config.diskEraseWithSecure(state)).toBe("bar");
    });
  });

  describe("diskEraseWithQuick", () => {
    it("returns MAAS config for enabling disk erase with quick erase", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.DISK_ERASE_WITH_QUICK_ERASE,
              value: "baz",
            }),
          ],
        }),
      });
      expect(config.diskEraseWithQuick(state)).toBe("baz");
    });
  });

  describe("httpProxy", () => {
    it("returns MAAS config for http proxy", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({ name: ConfigNames.HTTP_PROXY, value: "foo" }),
          ],
        }),
      });
      expect(config.httpProxy(state)).toBe("foo");
    });
  });

  describe("enableHttpProxy", () => {
    it("returns MAAS config for enabling httpProxy", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.ENABLE_HTTP_PROXY,
              value: "bar",
            }),
          ],
        }),
      });
      expect(config.enableHttpProxy(state)).toBe("bar");
    });
  });

  describe("usePeerProxy", () => {
    it("returns MAAS config for enabling peer proxy", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({ name: ConfigNames.USE_PEER_PROXY, value: "baz" }),
          ],
        }),
      });
      expect(config.usePeerProxy(state)).toBe("baz");
    });
  });

  describe("proxyType", () => {
    it("returns 'noProxy' if enable_http_proxy is false", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.ENABLE_HTTP_PROXY,
              value: false,
            }),
          ],
        }),
      });
      expect(config.proxyType(state)).toBe("noProxy");
    });

    it("returns 'builtInProxy' if enable_http_proxy is true and http_proxy is empty", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.ENABLE_HTTP_PROXY,
              value: true,
            }),
            factory.config({ name: ConfigNames.HTTP_PROXY, value: "" }),
          ],
        }),
      });
      expect(config.proxyType(state)).toBe("builtInProxy");
    });

    it("returns 'externalProxy' if enable_http_proxy is true and http_proxy is not empty", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.ENABLE_HTTP_PROXY,
              value: true,
            }),
            factory.config({
              name: ConfigNames.HTTP_PROXY,
              value: "http://www.url.com",
            }),
          ],
        }),
      });
      expect(config.proxyType(state)).toBe("externalProxy");
    });

    it("returns 'peerProxy' if enable_http_proxy is true, http_proxy is not empty and use_peer_proxy is true", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.ENABLE_HTTP_PROXY,
              value: true,
            }),
            factory.config({
              name: ConfigNames.HTTP_PROXY,
              value: "http://www.url.com",
            }),
            factory.config({ name: ConfigNames.USE_PEER_PROXY, value: true }),
          ],
        }),
      });
      expect(config.proxyType(state)).toBe("peerProxy");
    });
  });

  describe("maasName", () => {
    it("returns MAAS config for maas name", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.MAAS_NAME,
              value: "bionic-maas",
            }),
          ],
        }),
      });
      expect(config.maasName(state)).toBe("bionic-maas");
    });
  });

  describe("analyticsEnabled", () => {
    it("returns MAAS config for enable analytics", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({ name: ConfigNames.ENABLE_ANALYTICS, value: true }),
          ],
        }),
      });
      expect(config.analyticsEnabled(state)).toBe(true);
    });
  });

  describe("commissioningDistroSeries", () => {
    it("returns MAAS config for commissioning distro series", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.COMMISSIONING_DISTRO_SERIES,
              value: "bionic",
            }),
          ],
        }),
      });
      expect(config.commissioningDistroSeries(state)).toBe("bionic");
    });
  });

  describe("distroSeriesOptions", () => {
    it("returns array of distro series options, formatted as objects", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.COMMISSIONING_DISTRO_SERIES,
              value: "bionic",
              choices: [["bionic", "Ubuntu 18.04 LTS 'Bionic-Beaver'"]],
            }),
          ],
        }),
      });
      expect(config.distroSeriesOptions(state)).toStrictEqual([
        {
          value: "bionic",
          label: "Ubuntu 18.04 LTS 'Bionic-Beaver'",
        },
      ]);
    });
  });

  describe("defaultMinKernelVersion", () => {
    it("returns MAAS config for default kernel version", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.DEFAULT_MIN_HWE_KERNEL,
              value: "",
            }),
          ],
        }),
      });
      expect(config.defaultMinKernelVersion(state)).toBe("");
    });
  });

  describe("kernelParams", () => {
    it("returns MAAS config for kernel parameters", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({ name: ConfigNames.KERNEL_OPTS, value: "foo" }),
          ],
        }),
      });
      expect(config.kernelParams(state)).toBe("foo");
    });
  });

  describe("windowsKmsHost", () => {
    it("returns Windows KMS host", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.WINDOWS_KMS_HOST,
              value: "127.0.0.1",
            }),
          ],
        }),
      });
      expect(config.windowsKmsHost(state)).toBe("127.0.0.1");
    });
  });

  describe("vCenterServer", () => {
    it("returns vCenter server", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.VCENTER_SERVER,
              value: "my server",
            }),
          ],
        }),
      });
      expect(config.vCenterServer(state)).toBe("my server");
    });
  });

  describe("vCenterUsername", () => {
    it("returns vCenter username", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.VCENTER_USERNAME,
              value: "admin",
            }),
          ],
        }),
      });
      expect(config.vCenterUsername(state)).toBe("admin");
    });
  });

  describe("vCenterPassword", () => {
    it("returns vCenter password", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.VCENTER_PASSWORD,
              value: "passwd",
            }),
          ],
        }),
      });
      expect(config.vCenterPassword(state)).toBe("passwd");
    });
  });

  describe("vCenterDatacenter", () => {
    it("returns vCenter datacenter", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.VCENTER_DATACENTER,
              value: "my datacenter",
            }),
          ],
        }),
      });
      expect(config.vCenterDatacenter(state)).toBe("my datacenter");
    });
  });

  describe("thirdPartyDriversEnabled", () => {
    it("returns value of enable_third_party_drivers", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.ENABLE_THIRD_PARTY_DRIVERS,
              value: true,
            }),
          ],
        }),
      });
      expect(config.thirdPartyDriversEnabled(state)).toBe(true);
    });
  });

  describe("defaultOSystem", () => {
    it("returns MAAS config for default OS", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.DEFAULT_OSYSTEM,
              value: "bionic",
            }),
          ],
        }),
      });
      expect(config.defaultOSystem(state)).toBe("bionic");
    });
  });

  describe("defaultOSystemOptions", () => {
    it("returns array of default OS options, formatted as objects", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.DEFAULT_OSYSTEM,
              value: "ubuntu",
              choices: [
                ["centos", "CentOS"],
                ["ubuntu", "Ubuntu"],
              ],
            }),
          ],
        }),
      });
      expect(config.defaultOSystemOptions(state)).toStrictEqual([
        {
          value: "centos",
          label: "CentOS",
        },
        {
          value: "ubuntu",
          label: "Ubuntu",
        },
      ]);
    });
  });

  describe("defaultDistroSeries", () => {
    it("returns MAAS config for default distro series", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.DEFAULT_DISTRO_SERIES,
              value: "bionic",
            }),
          ],
        }),
      });
      expect(config.defaultDistroSeries(state)).toBe("bionic");
    });
  });

  describe("completedIntro", () => {
    it("returns MAAS config for completed intro", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({ name: ConfigNames.COMPLETED_INTRO, value: true }),
          ],
        }),
      });
      expect(config.completedIntro(state)).toBe(true);
    });
  });

  describe("releaseNotifications", () => {
    it("returns MAAS config for release notifications", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.RELEASE_NOTIFICATIONS,
              value: true,
            }),
          ],
        }),
      });
      expect(config.releaseNotifications(state)).toBe(true);
    });
  });

  describe("maasUrl", () => {
    it("returns MAAS config for MAAS URL", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.MAAS_URL,
              value: "http://1.2.3.4/MAAS",
            }),
          ],
        }),
      });
      expect(config.maasUrl(state)).toBe("http://1.2.3.4/MAAS");
    });
  });

  describe("rpcSharedSecret", () => {
    it("returns MAAS config for RPC shared secret", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.RPC_SHARED_SECRET,
              value: "veryverysecret",
            }),
          ],
        }),
      });
      expect(config.rpcSharedSecret(state)).toBe("veryverysecret");
    });
  });

  describe("sessionLength", () => {
    it("returns MAAS config for sessionLength", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.SESSION_LENGTH,
              value: 42069,
            }),
          ],
        }),
      });
      expect(config.sessionLength(state)).toBe(42069);
    });
  });

  describe("tlsCertExpirationNotificationEnabled", () => {
    it("returns MAAS config for TLS cert expiration notification enabled", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.TLS_CERT_EXPIRATION_NOTIFICATION_ENABLED,
              value: true,
            }),
          ],
        }),
      });
      expect(config.tlsCertExpirationNotificationEnabled(state)).toBe(true);
    });
  });

  describe("tlsCertExpirationNotificationInterval", () => {
    it("returns MAAS config for TLS cert expiration notification interval", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.TLS_CERT_EXPIRATION_NOTIFICATION_INTERVAL,
              value: 45,
            }),
          ],
        }),
      });
      expect(config.tlsCertExpirationNotificationInterval(state)).toBe(45);
    });
  });

  describe("kernelCrashDump", () => {
    it("returns MAAS config for kernel crash dump", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({
              name: ConfigNames.ENABLE_KERNEL_CRASH_DUMP,
              value: true,
            }),
          ],
        }),
      });
      expect(config.enableKernelCrashDump(state)).toBe(true);
    });
  });
});
