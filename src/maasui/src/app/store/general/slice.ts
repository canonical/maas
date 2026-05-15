import type { PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import type { GeneralState, GenerateCertificateParams } from "./types";
import { GeneralMeta } from "./types";

const generateInitialState = <K extends keyof GeneralState>(
  queryData: GeneralState[K]["data"]
) => ({
  data: queryData,
  errors: null,
  loaded: false,
  loading: false,
});

const generatePrepareReducer = (method: string) => ({
  prepare: () => ({
    meta: {
      cache: true,
      model: GeneralMeta.MODEL,
      method,
    },
    payload: null,
  }),
  reducer: () => {},
});

const generateStartReducer =
  (key: keyof GeneralState) => (state: GeneralState) => {
    state[key].loading = true;
  };

const generateErrorReducer =
  (key: keyof GeneralState) =>
  (
    state: GeneralState,
    action: PayloadAction<GeneralState[typeof key]["errors"]>
  ) => {
    state[key].errors = action.payload;
    state[key].loading = false;
  };

const generateSuccessReducer =
  (key: keyof GeneralState) =>
  (
    state: GeneralState,
    action: PayloadAction<GeneralState[typeof key]["data"]>
  ) => {
    state[key].data = action.payload;
    state[key].loaded = true;
    state[key].loading = false;
  };

const generalSlice = createSlice({
  name: GeneralMeta.MODEL,
  initialState: {
    architectures: generateInitialState([]),
    bondOptions: generateInitialState(null),
    componentsToDisable: generateInitialState([]),
    defaultMinHweKernel: generateInitialState(""),
    generatedCertificate: generateInitialState(null),
    hweKernels: generateInitialState([]),
    installType: generateInitialState(""),
    knownArchitectures: generateInitialState([]),
    knownBootArchitectures: generateInitialState([]),
    maasURL: generateInitialState(""),
    machineActions: generateInitialState([]),
    osInfo: generateInitialState(null),
    pocketsToDisable: generateInitialState([]),
    powerTypes: generateInitialState([]),
    tlsCertificate: generateInitialState(null),
    vaultEnabled: generateInitialState(null),
    version: generateInitialState(""),
  } as GeneralState,
  reducers: {
    cleanupGeneratedCertificateErrors: (state) => {
      state.generatedCertificate.errors = null;
    },
    clearGeneratedCertificate: (state) => {
      state.generatedCertificate.data = null;
      state.generatedCertificate.errors = null;
      state.generatedCertificate.loaded = false;
      state.generatedCertificate.loading = false;
    },
    fetchArchitectures: generatePrepareReducer("architectures"),
    fetchArchitecturesStart: generateStartReducer("architectures"),
    fetchArchitecturesError: generateErrorReducer("architectures"),
    fetchArchitecturesSuccess: generateSuccessReducer("architectures"),
    fetchBondOptions: generatePrepareReducer("bond_options"),
    fetchBondOptionsStart: generateStartReducer("bondOptions"),
    fetchBondOptionsError: generateErrorReducer("bondOptions"),
    fetchBondOptionsSuccess: generateSuccessReducer("bondOptions"),
    fetchComponentsToDisable: generatePrepareReducer("components_to_disable"),
    fetchComponentsToDisableStart: generateStartReducer("componentsToDisable"),
    fetchComponentsToDisableError: generateErrorReducer("componentsToDisable"),
    fetchComponentsToDisableSuccess: generateSuccessReducer(
      "componentsToDisable"
    ),
    fetchDefaultMinHweKernel: generatePrepareReducer("default_min_hwe_kernel"),
    fetchDefaultMinHweKernelStart: generateStartReducer("defaultMinHweKernel"),
    fetchDefaultMinHweKernelError: generateErrorReducer("defaultMinHweKernel"),
    fetchDefaultMinHweKernelSuccess: generateSuccessReducer(
      "defaultMinHweKernel"
    ),
    fetchHweKernels: generatePrepareReducer("hwe_kernels"),
    fetchHweKernelsStart: generateStartReducer("hweKernels"),
    fetchHweKernelsError: generateErrorReducer("hweKernels"),
    fetchHweKernelsSuccess: generateSuccessReducer("hweKernels"),
    fetchInstallType: generatePrepareReducer("install_type"),
    fetchInstallTypeStart: generateStartReducer("installType"),
    fetchInstallTypeError: generateErrorReducer("installType"),
    fetchInstallTypeSuccess: generateSuccessReducer("installType"),
    fetchKnownArchitectures: generatePrepareReducer("known_architectures"),
    fetchKnownArchitecturesStart: generateStartReducer("knownArchitectures"),
    fetchKnownArchitecturesError: generateErrorReducer("knownArchitectures"),
    fetchKnownArchitecturesSuccess:
      generateSuccessReducer("knownArchitectures"),
    fetchKnownBootArchitectures: generatePrepareReducer(
      "known_boot_architectures"
    ),
    fetchKnownBootArchitecturesStart: generateStartReducer(
      "knownBootArchitectures"
    ),
    fetchKnownBootArchitecturesError: generateErrorReducer(
      "knownBootArchitectures"
    ),
    fetchKnownBootArchitecturesSuccess: generateSuccessReducer(
      "knownBootArchitectures"
    ),
    fetchMAASURL: generatePrepareReducer("maas_url"),
    fetchMAASURLStart: generateStartReducer("maasURL"),
    fetchMAASURLError: generateErrorReducer("maasURL"),
    fetchMAASURLSuccess: generateSuccessReducer("maasURL"),
    fetchMachineActions: generatePrepareReducer("machine_actions"),
    fetchMachineActionsStart: generateStartReducer("machineActions"),
    fetchMachineActionsError: generateErrorReducer("machineActions"),
    fetchMachineActionsSuccess: generateSuccessReducer("machineActions"),
    fetchOsInfo: generatePrepareReducer("osinfo"),
    fetchOsInfoStart: generateStartReducer("osInfo"),
    fetchOsInfoError: generateErrorReducer("osInfo"),
    fetchOsInfoSuccess: generateSuccessReducer("osInfo"),
    fetchPocketsToDisable: generatePrepareReducer("pockets_to_disable"),
    fetchPocketsToDisableStart: generateStartReducer("pocketsToDisable"),
    fetchPocketsToDisableError: generateErrorReducer("pocketsToDisable"),
    fetchPocketsToDisableSuccess: generateSuccessReducer("pocketsToDisable"),
    fetchPowerTypes: generatePrepareReducer("power_types"),
    fetchPowerTypesStart: generateStartReducer("powerTypes"),
    fetchPowerTypesError: generateErrorReducer("powerTypes"),
    fetchPowerTypesSuccess: generateSuccessReducer("powerTypes"),
    fetchTlsCertificate: generatePrepareReducer("tls_certificate"),
    fetchTlsCertificateStart: generateStartReducer("tlsCertificate"),
    fetchTlsCertificateError: generateErrorReducer("tlsCertificate"),
    fetchTlsCertificateSuccess: generateSuccessReducer("tlsCertificate"),
    fetchVaultEnabled: generatePrepareReducer("vault_enabled"),
    fetchVaultEnabledStart: generateStartReducer("vaultEnabled"),
    fetchVaultEnabledError: generateErrorReducer("vaultEnabled"),
    fetchVaultEnabledSuccess: generateSuccessReducer("vaultEnabled"),
    fetchVersion: generatePrepareReducer("version"),
    fetchVersionStart: generateStartReducer("version"),
    fetchVersionError: generateErrorReducer("version"),
    fetchVersionSuccess: generateSuccessReducer("version"),
    generateCertificate: {
      prepare: (params: GenerateCertificateParams) => ({
        meta: {
          model: GeneralMeta.MODEL,
          method: "generate_client_certificate",
        },
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    generateCertificateStart: generateStartReducer("generatedCertificate"),
    generateCertificateError: generateErrorReducer("generatedCertificate"),
    generateCertificateSuccess: generateSuccessReducer("generatedCertificate"),
  },
});

export const { actions } = generalSlice;

export default generalSlice.reducer;
