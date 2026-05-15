import osInfo from "./osInfo";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";

describe("osInfo selectors", () => {
  describe("get", () => {
    it("returns osInfo", () => {
      const data = factory.osInfo();
      const state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            data,
          }),
        }),
      });
      expect(osInfo.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns osInfo loading state", () => {
      const state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            loading: true,
          }),
        }),
      });
      expect(osInfo.loading(state)).toStrictEqual(true);
    });
  });

  describe("loaded", () => {
    it("returns osInfo loaded state", () => {
      const state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            loaded: true,
          }),
        }),
      });
      expect(osInfo.loaded(state)).toStrictEqual(true);
    });
  });

  describe("errors", () => {
    it("returns osInfo errors state", () => {
      const errors = "Cannot fetch os info.";
      const state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            errors,
          }),
        }),
      });
      expect(osInfo.errors(state)).toStrictEqual(errors);
    });
  });

  describe("getUbuntuKernelOptions", () => {
    it("returns options for supplied key", () => {
      const data = factory.osInfo({
        kernels: {
          ubuntu: {
            precise: [
              ["hwe-p", "precise (hwe-p)"],
              ["hwe-q", "precise (hwe-q)"],
            ],
            trusty: [
              ["hwe-t", "trusty (hwe-t)"],
              ["hwe-u", "trusty (hwe-u)"],
            ],
          },
        },
      });
      const state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            data,
          }),
        }),
      });
      expect(osInfo.getUbuntuKernelOptions(state, "precise")).toEqual([
        { value: "", label: "No minimum kernel" },
        { value: "hwe-p", label: "precise (hwe-p)" },
        { value: "hwe-q", label: "precise (hwe-q)" },
      ]);
    });

    it("handles no kernels", () => {
      const state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            data: null,
          }),
        }),
      });
      expect(osInfo.getUbuntuKernelOptions(state, "precise")).toEqual([
        { value: "", label: "No minimum kernel" },
      ]);
    });

    it("handles no ubuntu releases", () => {
      const data = factory.osInfo({
        kernels: {},
      });
      const state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            data,
          }),
        }),
      });
      expect(osInfo.getUbuntuKernelOptions(state, "precise")).toEqual([
        { value: "", label: "No minimum kernel" },
      ]);
    });
  });

  describe("getAllUbuntuKernelOptions", () => {
    it("returns all ubuntu kernel options", () => {
      const data = factory.osInfo({
        kernels: {
          ubuntu: {
            precise: [
              ["hwe-p", "precise (hwe-p)"],
              ["hwe-q", "precise (hwe-q)"],
            ],
            trusty: [
              ["hwe-t", "trusty (hwe-t)"],
              ["hwe-u", "trusty (hwe-u)"],
            ],
          },
        },
      });
      const state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            data,
          }),
        }),
      });
      expect(osInfo.getAllUbuntuKernelOptions(state)).toEqual({
        precise: [
          { value: "", label: "No minimum kernel" },
          { value: "hwe-p", label: "precise (hwe-p)" },
          { value: "hwe-q", label: "precise (hwe-q)" },
        ],
        trusty: [
          { value: "", label: "No minimum kernel" },
          { value: "hwe-t", label: "trusty (hwe-t)" },
          { value: "hwe-u", label: "trusty (hwe-u)" },
        ],
      });
    });

    it("handles no data", () => {
      const state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            data: null,
          }),
        }),
      });
      expect(osInfo.getAllUbuntuKernelOptions(state)).toEqual({});
    });
  });

  describe("getOsReleases", () => {
    const data = factory.osInfo({
      releases: [
        ["centos/centos66", "CentOS 6"],
        ["centos/centos70", "CentOS 7"],
        ["ubuntu/precise", "Ubuntu 12.04 LTS 'Precise Pangolin'"],
        ["ubuntu/trusty", "Ubuntu 14.04 LTS 'Trusty Tahr'"],
      ],
    });
    let state: RootState;

    beforeEach(() => {
      state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            data,
          }),
        }),
      });
    });

    it("returns and formats OS releases with centos argument", () => {
      expect(osInfo.getOsReleases(state, "centos")).toEqual([
        { value: "centos66", label: "CentOS 6" },
        { value: "centos70", label: "CentOS 7" },
      ]);
    });

    it("returns and formats OS releases with ubuntu argument", () => {
      expect(osInfo.getOsReleases(state, "ubuntu")).toEqual([
        {
          value: "precise",
          label: "Ubuntu 12.04 LTS 'Precise Pangolin'",
        },
        { value: "trusty", label: "Ubuntu 14.04 LTS 'Trusty Tahr'" },
      ]);
    });

    it("handles no data", () => {
      state.general.osInfo.data = null;
      expect(osInfo.getOsReleases(state, "ubuntu")).toEqual([]);
    });
  });

  describe("getAllOsReleases", () => {
    const data = factory.osInfo({
      osystems: [
        ["ubuntu", "Ubuntu"],
        ["centos", "CentOS"],
      ],
      releases: [
        ["centos/centos66", "CentOS 6"],
        ["centos/centos70", "CentOS 7"],
        ["ubuntu/precise", "Ubuntu 12.04 LTS 'Precise Pangolin'"],
        ["ubuntu/trusty", "Ubuntu 14.04 LTS 'Trusty Tahr'"],
      ],
    });
    let state: RootState;

    beforeEach(() => {
      state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            loading: false,
            loaded: true,
            data,
          }),
        }),
      });
    });

    it("returns an object with all OS releases", () => {
      expect(osInfo.getAllOsReleases(state)).toEqual({
        centos: [
          { value: "centos66", label: "CentOS 6" },
          { value: "centos70", label: "CentOS 7" },
        ],
        ubuntu: [
          { value: "precise", label: "Ubuntu 12.04 LTS 'Precise Pangolin'" },
          { value: "trusty", label: "Ubuntu 14.04 LTS 'Trusty Tahr'" },
        ],
      });
    });

    it("handles no data", () => {
      state.general.osInfo.data = null;
      expect(osInfo.getAllOsReleases(state)).toEqual({});
    });
  });

  describe("getLicensedOsReleases", () => {
    const data = factory.osInfo({
      osystems: [
        ["ubuntu", "Ubuntu"],
        ["windows", "Windows"],
      ],
      releases: [
        ["centos/centos66", "CentOS 6"],
        ["centos/centos70", "CentOS 7"],
        ["windows/win2012*", "Windows 2012 Server"],
      ],
    });
    let state: RootState;

    beforeEach(() => {
      state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            loading: false,
            loaded: true,
            data,
          }),
        }),
      });
    });

    it("returns only licensed releases", () => {
      expect(osInfo.getLicensedOsReleases(state)).toEqual({
        windows: [{ value: "win2012", label: "Windows 2012 Server" }],
      });
    });

    it("handles no data", () => {
      state.general.osInfo.data = null;
      expect(osInfo.getLicensedOsReleases(state)).toEqual({});
    });
  });

  describe("getLicensedOsystems", () => {
    const data = factory.osInfo({
      osystems: [
        ["ubuntu", "Ubuntu"],
        ["windows", "Windows"],
      ],
      releases: [
        ["centos/centos66", "CentOS 6"],
        ["centos/centos70", "CentOS 7"],
        ["windows/win2012*", "Windows 2012 Server"],
      ],
    });
    let state: RootState;

    beforeEach(() => {
      state = factory.rootState({
        general: factory.generalState({
          osInfo: factory.osInfoState({
            loading: false,
            loaded: true,
            data,
          }),
        }),
      });
    });

    it("returns only licensed operating systems", () => {
      expect(osInfo.getLicensedOsystems(state)).toEqual([
        ["windows", "Windows"],
      ]);
    });

    it("handles no data", () => {
      state.general.osInfo.data = null;
      expect(osInfo.getLicensedOsystems(state)).toEqual([]);
    });
  });
});
