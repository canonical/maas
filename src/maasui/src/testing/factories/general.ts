import { array, define } from "cooky-cutter";

import { PowerTypeNames } from "@/app/store/general/constants";
import type {
  Architecture,
  BondOptions,
  CertificateData,
  CertificateMetadata,
  Choice,
  ComponentToDisable,
  DefaultMinHweKernel,
  GeneratedCertificate,
  HWEKernel,
  KnownArchitecture,
  KnownBootArchitecture,
  MachineAction,
  OSInfo,
  OSInfoKernels,
  OSInfoOS,
  PocketToDisable,
  PowerField,
  PowerType,
  TLSCertificate,
  Version,
} from "@/app/store/general/types";
import {
  BootProtocol,
  DriverType,
  PowerFieldScope,
  PowerFieldType,
} from "@/app/store/general/types";
import type { UtcDatetime } from "@/app/store/types/model";
import { NodeActions } from "@/app/store/types/node";

export const architecture = define<Architecture>("amd64");

export const bondOptions = define<BondOptions>({
  lacp_rates: () => [],
  modes: () => [],
  xmit_hash_policies: () => [],
});

export const certificateData = define<CertificateData>({
  certificate: "certificate",
  private_key: "private_key",
});

export const certificateMetadata = define<CertificateMetadata>({
  CN: "certificate@vmhost",
  expiration: "Wed, 19 Feb. 2020 11:59:19",
  fingerprint:
    "00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00",
});

export const componentToDisable = define<ComponentToDisable>("restricted");

export const defaultMinHweKernel = define<DefaultMinHweKernel>("ga-18.04");

export const generatedCertificate = define<GeneratedCertificate>({
  ...certificateData(),
  ...certificateMetadata(),
});

export const hweKernel = define<HWEKernel>(["ga-18.04", "bionic"]);

export const knownArchitecture = define<KnownArchitecture>("amd64");

export const knownBootArchitecture = define<KnownBootArchitecture>({
  arch_octet: "00:00",
  bios_boot_method: "pxe",
  bootloader_arches: "i386/amd64",
  name: "pxe",
  protocol: BootProtocol.TFTP,
});

export const machineAction = define<MachineAction>({
  name: NodeActions.COMMISSION,
  sentence: "commissioned",
  title: "Commission...",
  type: "lifecycle",
});

export const osInfoOS = define<OSInfoOS>({
  bionic: () => [],
});

export const osInfoKernels = define<OSInfoKernels>({
  ubuntu: osInfoOS,
});

export const osInfo = define<OSInfo>({
  osystems: () => [],
  releases: () => [],
  kernels: osInfoKernels,
  default_osystem: "ubuntu",
  default_release: "bionic",
});

export const pocketToDisable = define<PocketToDisable>("updates");

export const powerFieldChoice = define<Choice>(["auto", "Automatic"]);

export const powerField = define<PowerField>({
  choices: () => [],
  default: "auto",
  field_type: PowerFieldType.STRING,
  label: (i: number) => `test-powerfield-label-${i}`,
  name: (i: number) => `test-powerfield-name-${i}`,
  required: false,
  scope: PowerFieldScope.BMC,
});

export const powerType = define<PowerType>({
  can_probe: false,
  chassis: false,
  description: "test description",
  driver_type: DriverType.POWER,
  fields: array(powerField),
  missing_packages: () => [],
  name: PowerTypeNames.MANUAL,
  queryable: false,
});

export const tlsCertificate = define<TLSCertificate>({
  certificate: "certificate",
  ...certificateMetadata(),
});

export const version = define<Version>("test version");

export const timestamp = (timestamp: string) =>
  timestamp !== undefined
    ? (timestamp as UtcDatetime)
    : ("Wed, 08 Jul. 2020 05:35:4" as UtcDatetime);
