import type { ValueOf } from "@canonical/react-components";

import type { PowerTypeNames } from "../constants";

import type {
  BondLacpRate,
  BondMode,
  BondXmitHashPolicy,
  BootProtocol,
  DriverType,
  PowerFieldScope,
  PowerFieldType,
} from "./enum";

import type { APIError } from "@/app/base/types";
import type { MachineActions } from "@/app/store/machine/types";

export type Architecture = string;

export type ArchitecturesState = {
  errors: APIError;
  data: Architecture[];
  loaded: boolean;
  loading: boolean;
};

export type BondModeOptions = [
  [BondMode.BALANCE_RR, BondMode.BALANCE_RR],
  [BondMode.ACTIVE_BACKUP, BondMode.ACTIVE_BACKUP],
  [BondMode.BALANCE_XOR, BondMode.BALANCE_XOR],
  [BondMode.BROADCAST, BondMode.BROADCAST],
  [BondMode.LINK_AGGREGATION, BondMode.LINK_AGGREGATION],
  [BondMode.BALANCE_TLB, BondMode.BALANCE_TLB],
  [BondMode.BALANCE_ALB, BondMode.BALANCE_ALB],
];

export type BondLacpRateOptions = [
  [BondLacpRate.FAST, BondLacpRate.FAST],
  [BondLacpRate.SLOW, BondLacpRate.SLOW],
];

export type BondXmitHashPolicyOptions = [
  [BondXmitHashPolicy.LAYER2, BondXmitHashPolicy.LAYER2],
  [BondXmitHashPolicy.LAYER2_3, BondXmitHashPolicy.LAYER2_3],
  [BondXmitHashPolicy.LAYER3_4, BondXmitHashPolicy.LAYER3_4],
  [BondXmitHashPolicy.ENCAP2_3, BondXmitHashPolicy.ENCAP2_3],
  [BondXmitHashPolicy.ENCAP3_4, BondXmitHashPolicy.ENCAP3_4],
];

export type BondOptions = {
  lacp_rates: BondLacpRateOptions;
  modes: BondModeOptions;
  xmit_hash_policies: BondXmitHashPolicyOptions;
};

export type BondOptionsState = {
  errors: APIError;
  data: BondOptions;
  loaded: boolean;
  loading: boolean;
};

export type CertificateData = {
  certificate: string;
  private_key: string;
};

export type CertificateMetadata = {
  CN: string;
  expiration: string;
  fingerprint: string;
};

export type ComponentToDisable = "multiverse" | "restricted" | "universe";

export type ComponentsToDisableState = {
  errors: APIError;
  data: ComponentToDisable[];
  loaded: boolean;
  loading: boolean;
};

export type DefaultMinHweKernel = string;

export type DefaultMinHweKernelState = {
  errors: APIError;
  data: DefaultMinHweKernel;
  loaded: boolean;
  loading: boolean;
};

export type GeneratedCertificate = CertificateData & CertificateMetadata;

export type GeneratedCertificateState = {
  errors: APIError;
  data: GeneratedCertificate | null;
  loaded: boolean;
  loading: boolean;
};

export type HWEKernel = [string, string];

export type HWEKernelsState = {
  errors: APIError;
  data: HWEKernel[];
  loaded: boolean;
  loading: boolean;
};

export type KnownArchitecture =
  | "amd64"
  | "arm64"
  | "armhf"
  | "i386"
  | "ppc64el"
  | "s390x";

export type KnownArchitecturesState = {
  errors: APIError;
  data: KnownArchitecture[];
  loaded: boolean;
  loading: boolean;
};

export type KnownBootArchitecture = {
  arch_octet: string | null;
  bios_boot_method: string;
  bootloader_arches: string;
  name: string;
  protocol: BootProtocol;
};

export type KnownBootArchitecturesState = {
  errors: APIError;
  data: KnownBootArchitecture[];
  loaded: boolean;
  loading: boolean;
};

export type MachineAction = {
  name: MachineActions;
  sentence: string;
  title: string;
  type: string;
};

export type MachineActionsState = {
  errors: APIError;
  data: MachineAction[];
  loaded: boolean;
  loading: boolean;
};

export type OSInfoOsKernelEntry = [string, string];

export type OSInfoOS = Record<string, [string, string][]>;

export type OSInfoKernels = Record<string, OSInfoOS>;

export type OSInfoOSystem = [string, string];

export type OSInfoRelease = [string, string];

export type OSInfo = {
  osystems: OSInfoOSystem[];
  releases: OSInfoRelease[];
  kernels: OSInfoKernels;
  default_osystem: string;
  default_release: string;
};

export type OSInfoState = {
  errors: APIError;
  data: OSInfo | null;
  loaded: boolean;
  loading: boolean;
};

export type PocketToDisable = "backports" | "security" | "updates";

export type PocketsToDisableState = {
  errors: APIError;
  data: PocketToDisable[];
  loaded: boolean;
  loading: boolean;
};

export type Choice = [string, string];

export type PowerField = {
  choices: Choice[];
  default: string[] | number | string;
  field_type: PowerFieldType;
  label: string;
  name: string;
  required: boolean;
  scope: PowerFieldScope;
};

export type PowerType = {
  can_probe: boolean;
  chassis: boolean;
  defaults?: {
    cores: number;
    memory: number;
    storage: number;
  };
  description: string;
  driver_type: DriverType;
  fields: PowerField[];
  missing_packages: string[];
  name: ValueOf<typeof PowerTypeNames>;
  queryable: boolean;
};

export type PowerTypesState = {
  errors: APIError;
  data: PowerType[];
  loaded: boolean;
  loading: boolean;
};

export type TLSCertificate = CertificateMetadata &
  Omit<CertificateData, "private_key">;

export type TLSCertificateState = {
  errors: APIError;
  data: TLSCertificate | null;
  loaded: boolean;
  loading: boolean;
};

export type VaultEnabledState = {
  errors: APIError;
  data: boolean;
  loaded: boolean;
  loading: boolean;
};

export type Version = string;

export type VersionState = {
  errors: APIError;
  data: Version;
  loaded: boolean;
  loading: boolean;
};

export type InstallType = string;

export type InstallTypeState = {
  errors: APIError;
  data: InstallType;
  loaded: boolean;
  loading: boolean;
};

export type MAASURLType = string;

export type MAASURLState = {
  errors: APIError;
  data: MAASURLType;
  loaded: boolean;
  loading: boolean;
};

export type GeneralState = {
  architectures: ArchitecturesState;
  bondOptions: BondOptionsState;
  componentsToDisable: ComponentsToDisableState;
  defaultMinHweKernel: DefaultMinHweKernelState;
  generatedCertificate: GeneratedCertificateState;
  hweKernels: HWEKernelsState;
  installType: InstallTypeState;
  knownArchitectures: KnownArchitecturesState;
  knownBootArchitectures: KnownBootArchitecturesState;
  maasURL: MAASURLState;
  machineActions: MachineActionsState;
  osInfo: OSInfoState;
  pocketsToDisable: PocketsToDisableState;
  powerTypes: PowerTypesState;
  tlsCertificate: TLSCertificateState;
  vaultEnabled: VaultEnabledState;
  version: VersionState;
};
