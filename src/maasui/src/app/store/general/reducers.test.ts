import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("general reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      architectures: {
        data: [],
        errors: null,
        loaded: false,
        loading: false,
      },
      bondOptions: {
        data: null,
        errors: null,
        loaded: false,
        loading: false,
      },
      componentsToDisable: {
        data: [],
        errors: null,
        loaded: false,
        loading: false,
      },
      defaultMinHweKernel: {
        data: "",
        errors: null,
        loaded: false,
        loading: false,
      },
      installType: {
        data: "",
        errors: null,
        loaded: false,
        loading: false,
      },
      generatedCertificate: {
        data: null,
        errors: null,
        loaded: false,
        loading: false,
      },
      hweKernels: {
        data: [],
        errors: null,
        loaded: false,
        loading: false,
      },
      knownArchitectures: {
        data: [],
        errors: null,
        loaded: false,
        loading: false,
      },
      knownBootArchitectures: {
        data: [],
        errors: null,
        loaded: false,
        loading: false,
      },
      maasURL: {
        data: "",
        errors: null,
        loaded: false,
        loading: false,
      },
      machineActions: {
        data: [],
        errors: null,
        loaded: false,
        loading: false,
      },
      osInfo: {
        data: null,
        errors: null,
        loaded: false,
        loading: false,
      },
      pocketsToDisable: {
        data: [],
        errors: null,
        loaded: false,
        loading: false,
      },
      powerTypes: {
        data: [],
        errors: null,
        loaded: false,
        loading: false,
      },
      tlsCertificate: {
        data: null,
        errors: null,
        loaded: false,
        loading: false,
      },
      vaultEnabled: {
        data: null,
        errors: null,
        loaded: false,
        loading: false,
      },
      version: {
        data: "",
        errors: null,
        loaded: false,
        loading: false,
      },
    });
  });

  it("reduces fetchBondOptionsStart", () => {
    const initialState = factory.generalState({
      bondOptions: factory.bondOptionsState({ loading: false }),
    });
    expect(reducers(initialState, actions.fetchBondOptionsStart())).toEqual(
      factory.generalState({
        bondOptions: factory.bondOptionsState({ loading: true }),
      })
    );
  });

  it("reduces fetchBondOptionsSuccess", () => {
    const initialState = factory.generalState({
      bondOptions: factory.bondOptionsState({
        data: undefined,
        loading: true,
        loaded: false,
      }),
    });
    const fetchedBondOptions = factory.bondOptions();
    expect(
      reducers(
        initialState,
        actions.fetchBondOptionsSuccess(fetchedBondOptions)
      )
    ).toEqual(
      factory.generalState({
        bondOptions: factory.bondOptionsState({
          data: fetchedBondOptions,
          loading: false,
          loaded: true,
        }),
      })
    );
  });

  it("reduces fetchBondOptionsError", () => {
    const initialState = factory.generalState({
      bondOptions: factory.bondOptionsState({
        errors: null,
        loaded: false,
        loading: true,
      }),
    });

    expect(
      reducers(
        initialState,
        actions.fetchBondOptionsError("Could not fetch bond options")
      )
    ).toEqual(
      factory.generalState({
        bondOptions: factory.bondOptionsState({
          errors: "Could not fetch bond options",
          loaded: false,
          loading: false,
        }),
      })
    );
  });

  it("reduces fetchTlsCertificateStart", () => {
    const initialState = factory.generalState({
      tlsCertificate: factory.tlsCertificateState({ loading: false }),
    });
    expect(reducers(initialState, actions.fetchTlsCertificateStart())).toEqual(
      factory.generalState({
        tlsCertificate: factory.tlsCertificateState({ loading: true }),
      })
    );
  });

  it("reduces fetchTlsCertificateSuccess", () => {
    const initialState = factory.generalState({
      tlsCertificate: factory.tlsCertificateState({
        data: null,
        loading: true,
        loaded: false,
      }),
    });
    const fetchedTlsCertificate = factory.tlsCertificate();
    expect(
      reducers(
        initialState,
        actions.fetchTlsCertificateSuccess(fetchedTlsCertificate)
      )
    ).toEqual(
      factory.generalState({
        tlsCertificate: factory.tlsCertificateState({
          data: fetchedTlsCertificate,
          loading: false,
          loaded: true,
        }),
      })
    );
  });

  it("reduces fetchTlsCertificateError", () => {
    const initialState = factory.generalState({
      tlsCertificate: factory.tlsCertificateState({
        errors: null,
        loaded: false,
        loading: true,
      }),
    });
    const error = "Could not fetch TLS certificate";

    expect(
      reducers(initialState, actions.fetchTlsCertificateError(error))
    ).toEqual(
      factory.generalState({
        tlsCertificate: factory.tlsCertificateState({
          errors: error,
          loaded: false,
          loading: false,
        }),
      })
    );
  });

  it("reduces generateCertificateStart", () => {
    const initialState = factory.generalState({
      generatedCertificate: factory.generatedCertificateState({
        loading: false,
      }),
    });

    expect(reducers(initialState, actions.generateCertificateStart())).toEqual(
      factory.generalState({
        generatedCertificate: factory.generatedCertificateState({
          loading: true,
        }),
      })
    );
  });

  it("reduces generateCertificateSuccess", () => {
    const certificate = factory.generatedCertificate();
    const initialState = factory.generalState({
      generatedCertificate: factory.generatedCertificateState({
        data: null,
        loaded: false,
        loading: true,
      }),
    });

    expect(
      reducers(initialState, actions.generateCertificateSuccess(certificate))
    ).toEqual(
      factory.generalState({
        generatedCertificate: factory.generatedCertificateState({
          data: certificate,
          loaded: true,
          loading: false,
        }),
      })
    );
  });

  it("reduces generateCertificateError", () => {
    const initialState = factory.generalState({
      generatedCertificate: factory.generatedCertificateState({
        errors: null,
        loaded: false,
        loading: true,
      }),
    });

    expect(
      reducers(
        initialState,
        actions.generateCertificateError("Could not generate certificate")
      )
    ).toEqual(
      factory.generalState({
        generatedCertificate: factory.generatedCertificateState({
          errors: "Could not generate certificate",
          loaded: false,
          loading: false,
        }),
      })
    );
  });

  it("reduces clearGeneratedCertificate", () => {
    const initialState = factory.generalState({
      generatedCertificate: factory.generatedCertificateState({
        data: factory.generatedCertificate(),
        errors: "Uh oh",
        loaded: true,
        loading: true,
      }),
    });

    expect(reducers(initialState, actions.clearGeneratedCertificate())).toEqual(
      factory.generalState({
        generatedCertificate: factory.generatedCertificateState({
          data: null,
          errors: null,
          loaded: false,
          loading: false,
        }),
      })
    );
  });

  it("reduces cleanupGeneratedCertificateErrors", () => {
    const cert = factory.generatedCertificate();
    const initialState = factory.generalState({
      generatedCertificate: factory.generatedCertificateState({
        data: cert,
        errors: "Uh oh",
        loaded: true,
        loading: true,
      }),
    });

    expect(
      reducers(initialState, actions.cleanupGeneratedCertificateErrors())
    ).toEqual(
      factory.generalState({
        generatedCertificate: factory.generatedCertificateState({
          data: cert,
          errors: null,
          loaded: true,
          loading: true,
        }),
      })
    );
  });
});
