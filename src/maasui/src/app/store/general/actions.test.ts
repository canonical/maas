import { generalActions } from "./";

describe("general actions", () => {
  it("should handle fetching architectures", () => {
    expect(generalActions.fetchArchitectures()).toEqual({
      type: "general/fetchArchitectures",
      meta: {
        cache: true,
        model: "general",
        method: "architectures",
      },
      payload: null,
    });
  });

  it("should handle fetching bond options", () => {
    expect(generalActions.fetchBondOptions()).toEqual({
      type: "general/fetchBondOptions",
      meta: {
        cache: true,
        model: "general",
        method: "bond_options",
      },
      payload: null,
    });
  });

  it("should handle fetching boot architectures", () => {
    expect(generalActions.fetchKnownBootArchitectures()).toEqual({
      type: "general/fetchKnownBootArchitectures",
      meta: {
        cache: true,
        model: "general",
        method: "known_boot_architectures",
      },
      payload: null,
    });
  });

  it("should handle fetching components to disable", () => {
    expect(generalActions.fetchComponentsToDisable()).toEqual({
      type: "general/fetchComponentsToDisable",
      meta: {
        cache: true,
        model: "general",
        method: "components_to_disable",
      },
      payload: null,
    });
  });

  it("should handle fetching default min hwe kernel", () => {
    expect(generalActions.fetchDefaultMinHweKernel()).toEqual({
      type: "general/fetchDefaultMinHweKernel",
      meta: {
        cache: true,
        model: "general",
        method: "default_min_hwe_kernel",
      },
      payload: null,
    });
  });

  it("should handle fetching hwe kernels", () => {
    expect(generalActions.fetchHweKernels()).toEqual({
      type: "general/fetchHweKernels",
      meta: {
        cache: true,
        model: "general",
        method: "hwe_kernels",
      },
      payload: null,
    });
  });

  it("should handle fetching known architectures", () => {
    expect(generalActions.fetchKnownArchitectures()).toEqual({
      type: "general/fetchKnownArchitectures",
      meta: {
        cache: true,
        model: "general",
        method: "known_architectures",
      },
      payload: null,
    });
  });

  it("should handle fetching machine actions", () => {
    expect(generalActions.fetchMachineActions()).toEqual({
      type: "general/fetchMachineActions",
      meta: {
        cache: true,
        model: "general",
        method: "machine_actions",
      },
      payload: null,
    });
  });

  it("should handle fetching osinfo", () => {
    expect(generalActions.fetchOsInfo()).toEqual({
      type: "general/fetchOsInfo",
      meta: {
        cache: true,
        model: "general",
        method: "osinfo",
      },
      payload: null,
    });
  });

  it("should handle fetching pockets to disable", () => {
    expect(generalActions.fetchPocketsToDisable()).toEqual({
      type: "general/fetchPocketsToDisable",
      meta: {
        cache: true,
        model: "general",
        method: "pockets_to_disable",
      },
      payload: null,
    });
  });

  it("should handle fetching power types", () => {
    expect(generalActions.fetchPowerTypes()).toEqual({
      type: "general/fetchPowerTypes",
      meta: {
        cache: true,
        model: "general",
        method: "power_types",
      },
      payload: null,
    });
  });

  it("should handle fetching TLS certificate", () => {
    expect(generalActions.fetchTlsCertificate()).toEqual({
      type: "general/fetchTlsCertificate",
      meta: {
        cache: true,
        model: "general",
        method: "tls_certificate",
      },
      payload: null,
    });
  });

  it("should handle fetching Vault enabled status", () => {
    expect(generalActions.fetchVaultEnabled()).toEqual({
      type: "general/fetchVaultEnabled",
      meta: {
        cache: true,
        model: "general",
        method: "vault_enabled",
      },
      payload: null,
    });
  });

  it("should handle fetching version", () => {
    expect(generalActions.fetchVersion()).toEqual({
      type: "general/fetchVersion",
      meta: {
        cache: true,
        model: "general",
        method: "version",
      },
      payload: null,
    });
  });

  it("should handle generating a certificate", () => {
    expect(generalActions.generateCertificate({ object_name: "name" })).toEqual(
      {
        type: "general/generateCertificate",
        meta: {
          model: "general",
          method: "generate_client_certificate",
        },
        payload: {
          params: {
            object_name: "name",
          },
        },
      }
    );
  });
});
